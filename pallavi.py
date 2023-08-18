from flask import Flask, jsonify
import requests

app = Flask(__name__)

def call_external_api():
    url = "http://10.20.100.30:5001/inventory/view"  # Replace with the actual external API URL
    response = requests.get(url)

    if response.status_code == 200:
        try:
            external_data = response.json()
            return external_data
        except ValueError:
            return {"error": "Response is not valid JSON"}
    else:
        return {"error": f"GET request failed with status code: {response.status_code}"}

@app.route('/get_external_data', methods=['GET'])
def get_external_data():
    external_data = call_external_api()
    return jsonify(external_data)

if __name__ == '__main__':
    app.run(debug=True,host="10.20.100.30",port=8000)
