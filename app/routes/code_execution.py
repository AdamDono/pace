"""
Server-side code execution endpoint for compiled languages (Java, C++)
Handles secure sandboxed execution with timeouts
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required
import subprocess
import tempfile
import os
import shutil
from pathlib import Path

code_execution_bp = Blueprint('code_execution', __name__, url_prefix='/api')

# Security settings
MAX_EXECUTION_TIME = 5  # seconds
MAX_OUTPUT_SIZE = 10000  # characters

@code_execution_bp.route('/execute-code', methods=['POST'])
@login_required
def execute_code():
    """
    Execute code server-side for compiled languages
    Supports: Java, C++
    """
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', '').lower()

        if not code:
            return jsonify({
                'success': False,
                'error': 'No code provided'
            }), 400

        if language not in ['java', 'cpp', 'c++']:
            return jsonify({
                'success': False,
                'error': f'Server execution not supported for {language}'
            }), 400

        # Execute based on language
        if language == 'java':
            result = execute_java(code)
        elif language in ['cpp', 'c++']:
            result = execute_cpp(code)
        else:
            result = {'success': False, 'error': 'Unsupported language'}

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Execution error: {str(e)}'
        }), 500


def execute_java(code):
    """Execute Java code"""
    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='java_exec_')
        
        # Extract class name from code
        class_name = extract_java_class_name(code)
        if not class_name:
            return {'success': False, 'error': 'No public class found. Please define a public class with main method.'}

        # Write code to file
        java_file = os.path.join(temp_dir, f'{class_name}.java')
        with open(java_file, 'w') as f:
            f.write(code)

        # Compile Java
        compile_result = subprocess.run(
            ['javac', java_file],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            cwd=temp_dir
        )

        if compile_result.returncode != 0:
            return {
                'success': False,
                'error': f'Compilation Error:\n{compile_result.stderr}'
            }

        # Run Java
        run_result = subprocess.run(
            ['java', class_name],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            cwd=temp_dir
        )

        output = run_result.stdout
        error = run_result.stderr

        if run_result.returncode != 0 and error:
            return {
                'success': False,
                'error': f'Runtime Error:\n{error}'
            }

        return {
            'success': True,
            'output': output[:MAX_OUTPUT_SIZE] if output else '(No output)'
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'Execution timeout ({MAX_EXECUTION_TIME}s). Your code may have an infinite loop.'
        }
    except FileNotFoundError:
        return {
            'success': False,
            'error': 'Java compiler not found. Please ensure JDK is installed on the server.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }
    finally:
        # Cleanup
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def execute_cpp(code):
    """Execute C++ code"""
    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='cpp_exec_')
        
        # Write code to file
        cpp_file = os.path.join(temp_dir, 'main.cpp')
        with open(cpp_file, 'w') as f:
            f.write(code)

        # Compile C++
        exe_file = os.path.join(temp_dir, 'program')
        compile_result = subprocess.run(
            ['g++', cpp_file, '-o', exe_file, '-std=c++17'],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            cwd=temp_dir
        )

        if compile_result.returncode != 0:
            return {
                'success': False,
                'error': f'Compilation Error:\n{compile_result.stderr}'
            }

        # Run executable
        run_result = subprocess.run(
            [exe_file],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            cwd=temp_dir
        )

        output = run_result.stdout
        error = run_result.stderr

        if run_result.returncode != 0 and error:
            return {
                'success': False,
                'error': f'Runtime Error:\n{error}'
            }

        return {
            'success': True,
            'output': output[:MAX_OUTPUT_SIZE] if output else '(No output)'
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'Execution timeout ({MAX_EXECUTION_TIME}s). Your code may have an infinite loop.'
        }
    except FileNotFoundError:
        return {
            'success': False,
            'error': 'C++ compiler not found. Please ensure g++ is installed on the server.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }
    finally:
        # Cleanup
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def extract_java_class_name(code):
    """Extract the public class name from Java code"""
    import re
    match = re.search(r'public\s+class\s+(\w+)', code)
    if match:
        return match.group(1)
    # Fallback: try to find any class
    match = re.search(r'class\s+(\w+)', code)
    return match.group(1) if match else None
