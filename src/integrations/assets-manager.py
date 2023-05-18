from flask import Flask, render_template, request, redirect, url_for
import requests

app = Flask(__name__)

assets = [
    {'id': 1, 'name': 'asset1', 'type': 'dashboards', 'status': 'not_loaded'},
    {'id': 2, 'name': 'asset2', 'type': 'mappings', 'status': 'not_loaded'},
    # Add more assets here
]

# mock containers data
containers = [
    {"name": "accounting-service", "state": "Up", "ports": ""},
    {"name": "ad-service", "state": "Up", "ports": "0.0.0.0:52606->9555/tcp"},
    {"name": "cart-service", "state": "Up", "ports": "0.0.0.0:52603->7070/tcp"},
    {"name": "checkout-service", "state": "Up", "ports": "0.0.0.0:53314->5050/tcp"},
    {"name": "currency-service", "state": "Up", "ports": "0.0.0.0:52599->7001/tcp"},
    {"name": "data-prepper", "state": "Up", "ports": "0.0.0.0:21890->21890/tcp"},
    {"name": "email-service", "state": "Up", "ports": "0.0.0.0:52598->6060/tcp"},
    {"name": "feature-flag-service", "state": "Up (healthy)", "ports": "0.0.0.0:52619->50053/tcp, 0.0.0.0:8881->8881/tcp"},
    {"name": "fluentbit", "state": "Up", "ports": "2020/tcp, 0.0.0.0:24224->24224/tcp, 0.0.0.0:24224->24224/udp"},
    {"name": "frontend", "state": "Up", "ports": "0.0.0.0:8080->8080/tcp"},
    {"name": "opensearch-node1", "state": "Up (unhealthy)", "ports": "0.0.0.0:9200->9200/tcp, 9300/tcp, 0.0.0.0:9600->9600/tcp, 9650/tcp"},
    {"name": "opensearch-node2", "state": "Up", "ports": "9200/tcp, 9300/tcp, 9600/tcp, 9650/tcp"},
]

types = ['dashboards','mappings','queries' ]

def get_assets():
    return assets

def get_types():
    return types

def get_containers():
    return containers

@app.route('/')
def home():
    assets = get_assets()
    types = get_types()  # Add a function to get the list of types
    containers = get_containers()
    return render_template('index.html', assets=assets, types=types, containers=containers)

@app.route('/filter/<asset_type>', methods=['GET'])
def filter_assets(asset_type):
    # Filter the assets by type
    filtered_assets = [asset for asset in assets if asset.type == asset_type]
    return render_template('index.html', assets=filtered_assets)

@app.route('/delete_asset/<asset_id>', methods=['POST'])
def delete_asset(asset_id):
    # Add your logic here to delete the asset from OpenSearch
    return redirect(url_for('home'))

@app.route('/load_asset/<int:asset_id>')
def load_asset(asset_id):
    # Find the asset by its id
    asset = next((a for a in assets if a['id'] == asset_id), None)
    if asset and asset['status'] == 'not_loaded':
        # Put your OpenSearch upload code here
        # If the upload is successful, change the asset status
        asset['status'] = 'loaded'
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
