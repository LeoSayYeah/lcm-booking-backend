import os
from datetime import datetime, date, time, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from .models import Base, Service, Booking, BookingService
from .utils import within_hours, is_weekday, after_launch, send_email, WORK_START, WORK_END, LAUNCH_DATE

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///lcm.db')

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

engine = create_engine(DATABASE_URL, echo=False, future=True)
Base.metadata.create_all(engine)

ADMIN_KEY = os.getenv('ADMIN_KEY', 'change-this-admin-key')

# Seed services if empty
def seed_services():
    with Session(engine) as s:
        count = s.scalar(select(func.count(Service.id)))
        if count and count > 0:
            return
        # prices in pence, durations in minutes
        data = [
            # Oven Cleaning
            ('Oven Cleaning','Single oven clean', 5000, 90),
            ('Oven Cleaning','Oven and grill', 7500, 120),
            ('Oven Cleaning','Side by side single ovens', 9000, 120),
            ('Oven Cleaning','Range oven', 12500, 150),
            ('Oven Cleaning','Ceramic hob', 1000, 20),
            ('Oven Cleaning','Gas hob 4 burner', 2000, 30),
            ('Oven Cleaning','Extractor', 2000, 30),
            # Carpet Cleaning
            ('Carpet Cleaning','1 carpet', 5000, 60),
            ('Carpet Cleaning','2 carpets', 7000, 90),
            ('Carpet Cleaning','3 carpets', 9000, 90),
            ('Carpet Cleaning','4 carpets', 11000, 120),
            ('Carpet Cleaning','5 carpets', 12500, 120),
            ('Carpet Cleaning','Stairs & landing', 5000, 60),
            ('Carpet Cleaning','Stairs & landing x2', 7500, 90),
            # Sofa Cleaning
            ('Sofa Cleaning','Arm chair / love chair', 3000, 60),
            ('Sofa Cleaning','2 seater', 5000, 60),
            ('Sofa Cleaning','3 seater', 7500, 90),
            ('Sofa Cleaning','Corner sofa', 10000, 120),
            # White Goods
            ('White Goods','Washing machine service', 3000, 30),
            ('White Goods','Dishwasher service', 3000, 30),
            ('White Goods','Fridge freezer clean', 3000, 30),
            ('White Goods','American fridge freezer clean', 5000, 60),
        ]
        s.add_all([Service(category=c, name=n, price=p, duration_min=d) for c,n,p,d in data])
        s.commit()

seed_services()

@app.get('/health')
def health():
    return {'ok': True, 'time': datetime.utcnow().isoformat()}

@app.get('/services')
def get_services():
    with Session(engine) as s:
        rows = s.scalars(select(Service).order_by(Service.category, Service.id)).all()
        def ser(x: Service):
            return {
                'id': x.id,
                'category': x.category,
                'name': x.name,
                'price_pence': x.price,
                'duration_min': x.duration_min,
            }
        return jsonify([ser(r) for r in rows])

@app.post('/bookings')
def create_booking():
    data = request.get_json() or {}
    name = data.get('customer_name')
    email = data.get('email')
    phone = data.get('phone')
    address = data.get('address')
    postcode = data.get('postcode','').upper().strip()
    date_str = data.get('date')
    start_str = data.get('start_time')  # 'HH:MM'
    service_ids = data.get('service_ids', [])
    notes = data.get('notes')

    if not (name and address and postcode and date_str and start_str and service_ids):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        st_h, st_m = map(int, start_str.split(':'))
        st = time(st_h, st_m)
    except Exception:
        return jsonify({'error': 'Invalid date or time'}), 400

    if not is_weekday(d):
        return jsonify({'error': 'Bookings are Monday to Friday only'}), 400
    if not after_launch(d):
        return jsonify({'error': f'Bookings start from {LAUNCH_DATE.isoformat()}'}), 400

    with Session(engine) as s:
        svc = s.scalars(select(Service).where(Service.id.in_(service_ids))).all()
        if not svc:
            return jsonify({'error': 'No valid services selected'}), 400
        total_duration = sum(x.duration_min for x in svc)
        total_price = sum(x.price for x in svc)

        ok, end_t = within_hours(st, total_duration)
        if not ok:
            return jsonify({'error': f'Job would end at {end_t.strftime("%H:%M")}, which is after {WORK_END.strftime("%H:%M")}' }), 400

        b = Booking(
            customer_name=name,
            email=email,
            phone=phone,
            address=address,
            postcode=postcode,
            date=d,
            start_time=st,
            end_time=end_t,
            notes=notes,
            total_price_pence=total_price,
            total_duration_min=total_duration,
        )
        s.add(b)
        s.flush()
        s.add_all([BookingService(booking_id=b.id, service_id=x.id) for x in svc])
        s.commit()

    # Send email (best-effort)
    subj = f"LCM Booking Confirmation – {name} – {d.isoformat()} {st.strftime('%H:%M')}"
    body = f"Thank you for booking with LCM Oven Cleaning.\nDate: {d.isoformat()}\nStart: {st.strftime('%H:%M')}\nEnd: {end_t.strftime('%H:%M')}\nPostcode: {postcode}\nTotal: £{total_price/100:.2f}"
    send_email(subj, body, [os.getenv('EMAIL_TO', ''), email or ''])

    return jsonify({'ok': True, 'booking_id': b.id, 'end_time': end_t.strftime('%H:%M'), 'total_minutes': total_duration, 'total_price_pence': total_price})

@app.get('/bookings')
def list_bookings():
    # Admin list by date
    if request.headers.get('X-ADMIN-KEY') != ADMIN_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    date_str = request.args.get('date')
    with Session(engine) as s:
        q = select(Booking).order_by(Booking.date, Booking.start_time)
        if date_str:
            try:
                d = datetime.strptime(date_str, '%Y-%m-%d').date()
                q = q.where(Booking.date == d)
            except Exception:
                pass
        rows = s.scalars(q).all()
        res = []
        for r in rows:
            res.append({
                'id': r.id,
                'customer_name': r.customer_name,
                'email': r.email,
                'phone': r.phone,
                'address': r.address,
                'postcode': r.postcode,
                'date': r.date.isoformat(),
                'start_time': r.start_time.strftime('%H:%M'),
                'end_time': r.end_time.strftime('%H:%M'),
                'notes': r.notes,
                'total_price_pence': r.total_price_pence,
                'total_duration_min': r.total_duration_min,
            })
        return jsonify(res)

@app.post('/upload-media')
def upload_media():
    if request.headers.get('X-ADMIN-KEY') != ADMIN_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    os.makedirs('app/uploads', exist_ok=True)
    path = os.path.join('app/uploads', f.filename)
    f.save(path)
    return jsonify({'ok': True, 'filename': f.filename, 'url': f'/uploads/{f.filename}'})

@app.get('/uploads/<path:fname>')
def get_upload(fname):
    return send_from_directory('app/uploads', fname)

@app.get('/')
def root():
    return {'ok': True, 'service': 'LCM Booking Backend', 'launch_date': LAUNCH_DATE.isoformat()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
