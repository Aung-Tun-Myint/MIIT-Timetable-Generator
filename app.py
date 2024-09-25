import os
import threading
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
from werkzeug.utils import secure_filename
import pandas as pd
from markupsafe import Markup,escape


# Import your genetic algorithm timetable generation function
from timetable_generator import generate_timetables

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

# Configure upload and output folders
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure the upload and output directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Global variable to store progress
progress = {'status': 'idle', 'message': 'Waiting to start...', 'percentage': 0}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check if the files are present
        files = {
            'instructors_courses': request.files.get('instructors_courses'),
            'backlog': request.files.get('backlog'),
            'elective': request.files.get('elective')
        }

        missing_files = [name for name, file in files.items() if file is None or file.filename == '']
        if missing_files:
            return render_template('index.html', error=f"Missing files: {', '.join(missing_files)}")

        # Save the uploaded files
        for name, file in files.items():
            if file and allowed_file(file.filename):
                filename = secure_filename(name + '.csv')
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
            else:
                return render_template('index.html', error=f"Invalid file type for {name}. Only CSV files are allowed.")

        # Start the timetable generation in a separate thread
        thread = threading.Thread(target=run_timetable_generation)
        thread.start()

        return redirect(url_for('progress_page'))

    return render_template('index.html')

def run_timetable_generation():
    global progress
    progress['status'] = 'running'
    progress['message'] = 'Starting timetable generation...'
    progress['percentage'] = 0

    try:
        # Pass the file paths to your timetable generation function
        instructors_courses_path = os.path.join(app.config['UPLOAD_FOLDER'], 'instructors_courses.csv')
        backlog_path = os.path.join(app.config['UPLOAD_FOLDER'], 'backlog.csv')
        elective_path = os.path.join(app.config['UPLOAD_FOLDER'], 'elective.csv')

        generate_timetables(
            instructors_courses_path,
            backlog_path,
            elective_path,
            app.config['OUTPUT_FOLDER'],
            progress
        )

        progress['status'] = 'completed'
        progress['message'] = 'Timetable generation completed.'
        progress['percentage'] = 100
    except Exception as e:
        progress['status'] = 'error'
        progress['message'] = f"An error occurred: {str(e)}"
        progress['percentage'] = 0

@app.route('/progress')
def progress_page():
    return render_template('progress.html')

@app.route('/progress_status')
def progress_status():
    return jsonify(progress)

@app.route('/timetables')
def timetables():
    if progress.get('status') != 'completed':
        return redirect(url_for('index'))

    # Map timetable types to filenames
    timetable_files = {
        'Batch Timetables': 'Batch_Timetables.xlsx',
        'Instructor Timetables': 'Instructor_Timetables.xlsx',
        'Student Timetables': 'Elective_Backlog_Timetables.xlsx'
    }

    return render_template('timetables.html', timetable_files=timetable_files)

@app.route('/view_timetables/<timetable_type>')
def view_timetables(timetable_type):
    # Map timetable type to filename and display name
    if timetable_type == 'batch':
        filename = 'Batch_Timetables.xlsx'
        display_name = 'Batch Timetables'
    elif timetable_type == 'instructor':
        filename = 'Instructor_Timetables.xlsx'
        display_name = 'Instructor Timetables'
    elif timetable_type == 'student':
        filename = 'Elective_Backlog_Timetables.xlsx'
        display_name = 'Student Timetables'
    else:
        return redirect(url_for('timetables'))

    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if not os.path.exists(filepath):
        return redirect(url_for('timetables'))

    # Read Excel file sheets
    timetables = pd.read_excel(filepath, sheet_name=None)

    # Get list of timetable names (sheet names)
    timetable_names = sorted(timetables.keys())

    return render_template('view_timetables.html', timetable_type=timetable_type, display_name=display_name, timetable_names=timetable_names)


def style_table(df):
    # Apply custom styles to DataFrame
    styler = df.style

    # Replace NaN with empty strings
    styler = styler.format(na_rep='')

    # Set table attributes for Tailwind CSS
    styler.set_table_attributes('class="min-w-full border-collapse border border-gray-300"')

    # Apply inline styles directly for borders and formatting
    styler.set_table_styles([
        {'selector': 'thead', 'props': [('background-color', '#f9fafb'), ('border-bottom', '1px solid #d1d5db')]},
        {'selector': 'thead th', 'props': [('padding', '8px'), ('text-align', 'left'), ('border', '1px solid #d1d5db')]},
        {'selector': 'tbody td', 'props': [('padding', '8px'), ('border', '1px solid #d1d5db')]},
        {'selector': 'tbody tr:nth-child(even)', 'props': [('background-color', '#f9fafb')]},
        {'selector': 'tbody tr:nth-child(odd)', 'props': [('background-color', '#ffffff')]},
        {'selector': 'tbody tr:hover', 'props': [('background-color', '#f3f4f6')]}
    ], overwrite=False)

    # Render the styled DataFrame to HTML
    html = styler.to_html()

    return html

@app.route('/show_timetable/<timetable_type>/<timetable_name>')
def show_timetable(timetable_type, timetable_name):
    # Map timetable type to filename and display name
    if timetable_type == 'batch':
        filename = 'Batch_Timetables.xlsx'
        display_name = 'Batch Timetables'
    elif timetable_type == 'instructor':
        filename = 'Instructor_Timetables.xlsx'
        display_name = 'Instructor Timetables'
    elif timetable_type == 'student':
        filename = 'Elective_Backlog_Timetables.xlsx'
        display_name = 'Student Timetables'
    else:
        return redirect(url_for('timetables'))

    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if not os.path.exists(filepath):
        return redirect(url_for('timetables'))

    # Read the specific sheet (timetable) from the Excel file
    try:
        timetable_df = pd.read_excel(filepath, sheet_name=timetable_name, index_col=0)
    except ValueError:
        return redirect(url_for('view_timetables', timetable_type=timetable_type))

    # Replace '\n' with '<br>' in the DataFrame
    timetable_df = timetable_df.applymap(lambda x: x.replace('\n', '<br>') if isinstance(x, str) else x)

    # Apply styling to the DataFrame
    timetable_html = style_table(timetable_df)

    return render_template(
        'show_timetable.html',
        timetable_name=timetable_name,
        timetable_html=Markup(timetable_html),
        display_name=display_name,
        timetable_type=timetable_type
    )

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
