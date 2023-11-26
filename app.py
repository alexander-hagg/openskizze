from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

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
    <ul>
        <li>Die Strukturhöhe muss den Vorschriften der BauO NRW entsprechen.</li>
        <li>Die Bebauungsdichte sollte die lokale Gesetzgebung berücksichtigen.</li>
        <li>Öffentliche Zugänglichkeit muss in der Planung berücksichtigt werden.</li>
    </ul>
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
    selected_options = [key for key, value in selections.items() if value]
    if selected_options:
        # Generate a map name based on the selected options
        map_name = "_".join(selected_options)
        return f'/static/maps/{map_name}.png'
    return '/static/maps/default_map.png'  # A default map if no options are selected


if __name__ == '__main__':
    app.run(debug=True)
