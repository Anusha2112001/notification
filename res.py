from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse, abort
from pymongo import MongoClient
from bson.objectid import ObjectId
from flasgger import Swagger
import datetime
import csv, os, random, string
from bson import json_util
from werkzeug.datastructures import FileStorage
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate





app = Flask(__name__)
swagger = Swagger(app)
api = Api(app, version='1.0', title='Reservation API', description='API for Reservation Management')
mongo_client = MongoClient('mongodb://localhost:27017/')
db = mongo_client['reservationsample3_db3']
collection = db['reservations']

def send_email(user_email, email_subject, email_body):
    # Implement your email sending logic here
    msg = MIMEMultipart()
    msg['Subject'] = email_subject
    msg['From'] = 'noreply@library.com'
    msg['To'] = user_email

    body = MIMEText(email_body, 'plain')
    msg.attach(body)

    smtp_server = 'smtp.gmail.com'  # Update with your SMTP server details
    smtp_port = 587
    smtp_username = 'anushahs2112001@gmail.com'  # Replace with your Gmail email address
    smtp_password = 'rikp fpjk zfdm jmsf'  # Replace with your Gmail password or app-specific password

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail('noreply@library.com', user_email, msg.as_string())
        server.quit()
        print('Email sent successfully!')
    except Exception as e:
        print('An error occurred while sending the email:', str(e))

def send_due_date_reminder_email(data):
    # Your existing due date reminder email logic
    reserved_user = data['Reserved_user']
    user_email = data['User_email']
    inv_id = data['Inventory_id']
    inv_name = data['Inventory_name']
    due_date = data['Reservation_expiry_date']
    
    email_subject = f"Due date reminder for {inv_name} (ID: {inv_id})"
    email_body = f"Dear {reserved_user},\n\n" \
                  f"This is a reminder that your reservation for {inv_name} (ID: {inv_id}) is due on {due_date}.\n\n" \
                  f"Please return the resource to the library by the due date.\n\n" \
                  f"If you are unable to return the resource by the due date, please contact the library to extend your reservation.\n\n" \
                  f"Thank you,\nThe Library"
    
    send_email(user_email, email_subject, email_body)

def send_overdue_notification_email(data):
    # Your existing overdue notification email logic
    reserved_user = data['Reserved_user']
    user_email = data['User_email']
    inv_id = data['Inventory_id']
    inv_name = data['Inventory_name']
    due_date = data['Reservation_expiry_date']
    overdue_days = data['Overdue_days']
    
    email_subject = f"Overdue notification for {inv_name} (ID: {inv_id})"
    email_body = f"Dear {reserved_user},\n\n" \
                  f"Your reservation for {inv_name} (ID: {inv_id}) is overdue by {overdue_days} days.\n\n" \
                  f"The due date for the resource was {due_date}.\n\n" \
                  f"Please return the resource to the library as soon as possible.\n\n" \
                  f"If you have already returned the resource, please disregard this email.\n\n" \
                  f"Thank you,\nThe Library"
    
    send_email(user_email, email_subject, email_body)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

upload_model = api.model('UploadCSV', {
    'file': fields.Raw(required=True, description='CSV File')
})

def generate_reservation_id():
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f'r{timestamp}{random_suffix}'

"""
upload_parser = reqparse.RequestParser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True)
@api.route('/api/reservation/upload')
class UploadCSV(Resource):
    def post(self):
        if 'file' not in request.files:
            return {'error': 'No file part'}, 400
        file = request.files['file']
        if not file.filename:
            return {'error': 'No selected file'}, 400
        if file:
            # Clear existing data in the MongoDB collection
            collection.delete_many({})
            
            # Read and insert data from the CSV file into the MongoDB collection
            data = csv.DictReader(file.stream.read().decode('utf-8').splitlines())
            inserted_ids = []
            for row in data:
                result = collection.insert_one(row)
                inserted_ids.append(str(result.inserted_id))
            
            return {'inserted_ids': inserted_ids}, 201  # Fixed return statement
"""

upload_parser = reqparse.RequestParser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True)

@api.route('/inventory/upload')
class UploadCSV(Resource):
    @api.expect(upload_parser)
    def post(self):
        args = upload_parser.parse_args()
        uploaded_file = args['file']

        try:
            collection.delete_many({})  # Delete existing data
            data = csv.DictReader(uploaded_file.stream.read().decode('utf-8').splitlines())
            inserted_ids = []
            for row in data:
                result = collection.insert_one(row)
                inserted_ids.append(str(result.inserted_id))
            
            return {'message': 'Data uploaded successfully', 'inserted_ids': inserted_ids}, 200
        except Exception as e:
            return {'error': 'An error occurred while uploading data'}, 500



reservation_model = api.model('Reservation', {
    'reservation_id': fields.Integer(description='Reservation ID (Primary Key)'),
    'Reserved_user': fields.String(required=True, description='Name of the user making the reservation'),
    'Reservation_created_date': fields.DateTime(required=True, description='Date/Time of reservation creation'),
    'Inventory_logo': fields.String(required=True, description='URL of the inventory logo'),
    'Inventory_name': fields.String(required=True, description='Name of the inventory (URL)'),
    'Inventory_description': fields.String(required=True, description='Description of the inventory'),
    'Reservation_status': fields.String(required=True, description='Status of the reservation'),
    'Reservation_status_comments': fields.String(description='Additional comments on the reservation status'),
    'Reservation_expiry_date': fields.DateTime(required=True, description='Date/Time of reservation expiry'),
    'Books': fields.List(fields.String, description='List of reserved items')  # Include the contents field
})


@api.route('/reservations')
class Reservations(Resource):
    @api.doc(params={'page': 'Page number', 'limit': 'Reservations per page'}, description='View all reservations')
    def get(self):
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 5))

        total_reservations = collection.count_documents({})

        if page < 1:
            page = 1

        skip = (page - 1) * limit

        reservations = list(collection.find({}).skip(skip).limit(limit))

        for reservation in reservations:
            reservation['_id'] = str(reservation['_id'])
            #reservation['Reservation_created_date'] = reservation['Reservation_created_date'].isoformat()
            #reservation['Reservation_expiry_date'] = reservation['Reservation_expiry_date'].isoformat()

        return {
            'page': page,
            'limit': limit,
            'total_reservations': total_reservations,
            'reservations': reservations
        }


@api.route('/reservations/<string:reservation_id>')
class Reservation(Resource):
    @api.doc(description='View a reservation by ID')
    def get(self, reservation_id):
        reservation = collection.find_one({'reservation_id': int(reservation_id)})
        if reservation:
            reservation['_id'] = str(reservation['_id'])
            return {'reservation': reservation} 
        return {'message': 'Reservation not found'}, 404
    
    @api.doc(description='Update a reservation by ID', body=reservation_model)
    def put(self, reservation_id):
        reservation_data = api.payload
        existing_reservation = collection.find_one({'reservation_id': int(reservation_id)})
        if not existing_reservation:
            return {'message': 'Reservation not found'}, 404
        
        result = collection.update_one({'reservation_id': int(reservation_id)}, {'$set': reservation_data})
        if result.modified_count == 1:
            return {'message': 'Reservation updated successfully'}
        return {'message': 'Failed to update reservation'}, 500
    
    @api.doc(description='Delete a reservation by ID')
    def delete(self, reservation_id):
        existing_reservation = collection.find_one({'reservation_id': int(reservation_id)})
        if not existing_reservation:
            return {'message': 'Reservation not found'}, 404
        
        result = collection.delete_one({'reservation_id': int(reservation_id)})
        if result.deleted_count == 1:
            return {'message': 'Reservation deleted successfully'}
        return {'message': 'Failed to delete reservation'}, 500


@api.route('/reservations/create')
class CreateReservation(Resource):
    @api.doc(description='Create a new reservation', body=reservation_model)
    def post(self): 
        reservation_data = api.payload
        reservation_id = reservation_data.get('reservation_id')
        if not reservation_id:
            abort(400, error='reservation_id is required')

        existing_reservation = collection.find_one({'reservation_id': reservation_id})
        if existing_reservation:
            abort(400, error='A reservation with the same reservation_id already exists')

        user = reservation_data['Reserved_user']
        reservation_created_date = datetime.datetime.strptime(
            reservation_data['Reservation_created_date'], '%Y-%m-%dT%H:%M:%S.%fZ'
        )

        # Check if the user has reached the maximum reservations for this month
        current_month_start = reservation_created_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_end = current_month_start + datetime.timedelta(days=30)

        user_reservations_count = collection.count_documents({
            'Reserved_user': user,
            'Reservation_created_date': {
                '$gte': current_month_start,
                '$lt': current_month_end
            }
        })

        if user_reservations_count >= 3:
            abort(400, error='Maximum reservations reached for this month')

        new_reservation = {
            'reservation_id': reservation_id,
            'Reserved_user': user,
            'Reservation_created_date': reservation_created_date,
            'Inventory_logo': reservation_data['Inventory_logo'],
            'Inventory_name': reservation_data['Inventory_name'],
            'Inventory_description': reservation_data['Inventory_description'],
            'Reservation_status': 'Requested',
            'Reservation_status_comments': 'Waiting for approval',
            'Reservation_expiry_date': current_month_end,  # Expiry at the end of the month
            'Books': reservation_data['Books']
        }

        result = collection.insert_one(new_reservation)

        if result.inserted_id:
            inserted_id = str(result.inserted_id)
            # Calculate days until due date
            due_date = current_month_end
            days_until_due = (due_date - datetime.datetime.now()).days

            if 0 <= days_until_due <= 3:  # Adjust the threshold as needed
                notification_data = {
                    'Reserved_user': user,
                    'User_email': 'anushahs2112001@gmail.com',  # Replace with the user's email address
                    'Inventory_id': reservation_id,
                    'Inventory_name': new_reservation['Inventory_name'],
                    'Reservation_expiry_date': current_month_end,
                }
                send_due_date_reminder_email(notification_data)
                try:
                 send_overdue_notification_email(overdue_notification_data)
                except Exception as e:
                            print('An error occurred while sending overdue notification email:', str(e))

            
            
            if days_until_due >= 0:  # User didn't return the book on time
                  overdue_notification_data = {
                      'Reserved_user': user,
                       'User_email': 'anushahs2112001@gmail.com',  # Replace with the user's email address
                        'Inventory_id': reservation_id,
                        'Inventory_name': new_reservation['Inventory_name'],
                         'Reservation_expiry_date': current_month_end,
                       'Overdue_days': abs(days_until_due),
        }
        send_overdue_notification_email(overdue_notification_data)
        
        
    
        User_email = 'anushahs2112001@gmail.com'
        reservation_confirmation_subject = "Reservation Confirmation"
        reservation_confirmation_body = f"Dear {user},\n\n" \
                                            f"Your reservation for {new_reservation['Inventory_name']} (ID: {reservation_id}) " \
                                            f"has been successfully created.\n\n" \
                                            f"Reservation details:\n" \
                                            f"Inventory: {new_reservation['Inventory_name']}\n" \
                                            f"Reservation ID: {reservation_id}\n" \
                                            f"Expiry Date: {current_month_end}\n\n" \
                                            f"Thank you for using our reservation service!\n\n" \
                                            f"Best regards,\nThe Library" 
                                            
        send_email(User_email, reservation_confirmation_subject, reservation_confirmation_body)
        return {'message': 'Reservation created successfully', '_id': inserted_id}, 201
    
    


if __name__ == '__main__':
    app.run(debug=True, port=5003)
    
    
    