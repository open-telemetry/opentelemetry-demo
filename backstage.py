import os

# Template string for backstage.yaml
template = """
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: {service_name}
  description: This service is responsible to process a checkout order from the user. The checkout service will call many other services in order to process an order.
  annotations:
    backstage.io/techdocs-ref: url:https://opentelemetry.io/docs/demo/services/{service_name}/
spec:
  type: service
  lifecycle: production
  owner: user:guest
  system: opentelemetry-demo
"""

def create_backstage_file(directory):
    # Construct the file path for backstage.yaml
    backstage_file_path = os.path.join(directory, "backstage.yaml")
    
    # Extract the directory name from the full path
    directory_name = os.path.basename(directory)
    
    # Fill in the template with the directory name
    backstage_content = template.format(service_name=directory_name)
    
    # Write the content to the backstage.yaml file
    with open(backstage_file_path, 'w') as f:
        f.write(backstage_content)
    
    print(f"Created backstage.yaml in {directory}")

def scan_directories(root_directory):
    from pathlib import Path
    dirs = sorted([d for d in Path(root_directory).iterdir() if d.is_dir()])
    for entry in dirs:
        #create_backstage_file(entry)
        print(f'    - ./{entry}/backstage.yaml')

if __name__ == "__main__":
    root_directory = "./src"
    
    if not os.path.exists(root_directory):
        print("Root directory not found.")
    else:
        scan_directories(root_directory)