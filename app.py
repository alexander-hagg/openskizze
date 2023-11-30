from flask import Flask, jsonify, request, send_from_directory
from PIL import Image
import numpy as np
import os
from math import sqrt, floor


app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

def image_to_voxels(image_path):
    image = Image.open(image_path).convert('L')
    np_image = np.array(image)
    voxel_data = np_image / 255.0
    return voxel_data.tolist()

# @app.route('/get-voxel-meshes', methods=['GET'])
# def get_voxel_meshes():
#     n = 3  # number of rows and columns
#     voxel_meshes = []
#     for i in range(1, n**2 + 1):
#         image_path = f'res/{i}.png'
#         if not os.path.exists(image_path):
#             return jsonify({"error": f"Image {i}.png not found"}), 404
#         voxel_data = image_to_voxels(image_path)
#         voxel_meshes.append(voxel_data)
#     return jsonify(voxel_meshes)    

@app.route('/get-voxel-meshes', methods=['GET'])
def get_voxel_meshes():
    folder_path = 'res/'  # Folder containing PNG images
    files = os.listdir(folder_path)
    png_files = [file for file in files if file.lower().endswith('.png')]

    # Determine the number of rows and columns based on the number of images
    n = floor(sqrt(len(png_files)))
    # if n**2 != len(png_files):
    #     return jsonify({"error": "Number of images is not a perfect square"}), 400

    voxel_meshes = []
    for png_file in png_files:
        image_path = os.path.join(folder_path, png_file)
        voxel_data = image_to_voxels(image_path)
        voxel_meshes.append(voxel_data)
    return jsonify(voxel_meshes)

@app.route('/update_designs', methods=['POST'])
def update_designs():
    params = request.json
    design_src = generate_design_image_name(params)
    print(f'design_src: {design_src}')
    return jsonify({'design': design_src})

@app.route('/update_output_map', methods=['POST'])
def update_output_map():
    selections = request.json
    map_src = generate_output_map_name(selections)
    print(f'map_src: {map_src}')
    return jsonify({'mapSrc': map_src})

@app.route('/formalize_criteria', methods=['POST'])
def formalize_criteria():
    data = request.json
    # Simulate a call to a mockup LLM and return criteria
    criteria = mockup_llm_process(data)
    return jsonify({'criteria': criteria})

def mockup_llm_process(data):
    # Placeholder function for LLM processing
    # This should process 'data' and return a string with the criteria in German
    return '''
    <strong>Abgeleitete formale Kriterien:</strong>
    <ll>
        <li>HOCHB_WIND_01: Die Bauhöhe darf an den auf Karte b1 angegebene Positionen nur 7 Meter betragen.</li>
        <li>HOCHB_WIND_02: Die Bebauungsporösität muss mindestens 0.8 betragen und darf an den auf Karte c1 angegebene Positionen 0.3 nicht überschreiten.</li>
        <li>BEBAU_TEMP_01: An den auf Karte c2 Stellen muss grünblaue Infrastruktur eingeplant werden.</li>
        <li>STRUK_01: Die Bebauungsstruktur muss qualitativ die Strukturen der Planungsentwurfskategorien II-IV ähneln</li>
    </ll>
    '''

def generate_design_image_name(params):
    # Concatenate selected option values to form a unique image name
    image_name_parts = []
    for key, value in params.items():
        if value == 'on':
            image_name_parts.append(key)
        else:
            image_name_parts.append(value)
    image_name = "_".join(image_name_parts)
    # Assume all images are in the png format for simplicity
    return f'/static/img/{image_name}.png'


def generate_output_map_name(selections):
    print(f'selections: {selections}')
    selected_options = [key for key, value in selections.items() if value]
    if selected_options:
        # Generate a map name based on the selected options
        map_name = "_".join(selected_options)
        return f'/static/maps/{map_name}.png'
    return '/static/maps/default_map.png'  # A default map if no options are selected


if __name__ == '__main__':
    app.run(debug=True)
