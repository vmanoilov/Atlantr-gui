from flask import Flask, render_template, request, redirect, url_for
import subprocess
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run():
    input_file = request.form['input_file']
    output_file = request.form['output_file']
    threads = request.form['threads']
    matchers_file = request.form['matchers_file']
    timeout = request.form['timeout']
    invunma = 'invunma' in request.form
    grabber = 'grabber' in request.form

    if not os.path.isfile(input_file):
        return "Input file not found.", 400

    if not os.path.isdir(os.path.dirname(output_file)):
        return "Invalid output directory.", 400

    if not threads.isdigit():
        return "Threads must be a valid number.", 400

    if not timeout.isdigit():
        return "Timeout must be a valid number.", 400

    cmd = [
        "python", "atr3.py",
        "--input", input_file,
        "--output", output_file,
        "--threads", threads,
        "--timeout", timeout,
        "--invunma", str(invunma),
        "--grabber", str(grabber),
        "--matchfile", matchers_file
    ]

    def run_command():
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in process.stdout:
            print(line, end="")
        for line in process.stderr:
            print(line, end="")

    thread = Thread(target=run_command)
    thread.start()

    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
