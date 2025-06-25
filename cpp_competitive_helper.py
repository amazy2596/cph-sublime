# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 6.0 - [最终版] 实现可交互的、模仿 CPH 风格的 HTML UI
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json
import cgi
import time
import threading

# --- 全局变量 ---
# 追踪 UI 视图: { 'cpp_view_id': html_sheet_id }
ui_views = {}

# --- 辅助函数 ---

def find_sheet_by_id(window, sheet_id):
    """根据 id 寻找 sheet"""
    for sheet in window.sheets():
        if sheet.id() == sheet_id:
            return sheet
    return None

def generate_html(problem_name, test_cases, results={}):
    """根据测试数据和结果动态生成HTML"""
    styles = """
    <style>
        body { 
            --green: #2ea043; --red: #f14c4c; --yellow: #cca700;
            --blue: #0078d4; --bg-dark: #181818; --bg-light: #1f1f1f;
            --border: #454545; --text-light: #cccccc; --text-dark: #9d9d9d;
            font-family: sans-serif; background-color: var(--bg-dark); color: var(--text-light);
            padding: 15px;
        }
        a { text-decoration: none; color: var(--blue); }
        h1 { font-size: 1.5em; margin: 5px 0 20px 0; }
        details { 
            border-left: 4px solid var(--border);
            margin-bottom: 15px; background-color: var(--bg-light);
            padding: 10px;
        }
        details.state-passed { border-left-color: var(--green); }
        details.state-failed { border-left-color: var(--red); }
        details.state-running { border-left-color: var(--yellow); }
        summary {
            font-weight: bold; cursor: pointer;
            padding-bottom: 10px; list-style: none;
        }
        summary::-webkit-details-marker { display: none; }
        .case-header { display: block; }
        .case-title { color: var(--blue); vertical-align: middle; }
        .case-status { margin-left: 10px; font-weight: normal; }
        .case-status.passed { color: var(--green); }
        .case-status.failed { color: var(--red); }
        .case-status.running { color: var(--yellow); }
        .case-buttons { float: right; }
        .case-buttons a {
            color: white; border-radius: 3px;
            padding: 4px 8px; margin-left: 5px;
            font-family: sans-serif;
        }
        .run-btn { background-color: var(--green); }
        .del-btn { background-color: var(--red); }
        .content-block { border-top: 1px solid var(--border); padding-top: 10px; }
        h4 { margin: 10px 0 5px 0; color: var(--text-dark); font-size: 0.9em; font-weight: normal; }
        pre {
            white-space: pre-wrap; word-wrap: break-word;
            background-color: var(--bg-dark); padding: 10px;
            border-radius: 3px; font-family: monospace; margin: 0;
        }
    </style>
    """
    
    test_cases_html = ""
    for i, case in enumerate(test_cases):
        res = results.get(i, {})
        state = res.get('state', '') # 'passed', 'failed', 'running'
        
        status_html = ""
        if state == 'passed':
            status_html = "<span class='case-status passed'>Passed {}ms</span>".format(res.get('time', ''))
        elif state == 'failed':
            status_html = "<span class='case-status failed'>Failed {}ms</span>".format(res.get('time', ''))
        elif state == 'running':
            status_html = "<span class='case-status running'>Running</span>"

        run_url = sublime.command_url('cph_run_single_test', {'test_index': i})
        del_url = sublime.command_url('cph_delete_test', {'test_index': i})

        case_html = """
        <details class="state-{}" open>
            <summary>
                <div class="case-header">
                    <div class="case-buttons">
                        <a href="{}" class="run-btn">▶</a>
                        <a href="{}" class="del-btn">🗑️</a>
                    </div>
                    <span class="case-title">TC {}</span>
                    {}
                </div>
            </summary>
            <div class="content-block">
                <h4>Input:</h4><pre>{}</pre>
            </div>
            <div class="content-block">
                <h4>Expected Output:</h4><pre>{}</pre>
            </div>
        """.format(
            state, run_url, del_url, i + 1, status_html,
            cgi.escape(case.get('test', '')),
            "<br>".join([cgi.escape(ans) for ans in case.get('correct_answers', [])])
        )
        
        if state == 'failed':
            case_html += """
            <div class="content-block">
                <h4>Received Output:</h4><pre>{}</pre>
            </div>
            """.format(cgi.escape(res.get('output', '')))

        case_html += "</details>"
        test_cases_html += case_html

    final_html = styles + "<h1>{}</h1>".format(cgi.escape(problem_name)) + test_cases_html
    return final_html

def run_test_in_thread(cpp_view, test_index=-1):
    """在后台线程中运行测试的函数"""
    runner = TestRunner(cpp_view)
    runner.run_and_update(test_index)


# --- 命令定义 ---

class CphToggleUiCommand(sublime_plugin.WindowCommand):
    """主命令：打开或关闭 UI 面板"""
    def run(self):
        window = self.window
        cpp_view = window.active_view()
        if not cpp_view or not cpp_view.file_name(): return

        ui_sheet_id = ui_views.get(cpp_view.id())
        
        if ui_sheet_id:
            ui_sheet = find_sheet_by_id(window, ui_sheet_id)
            if ui_sheet: ui_sheet.close()
            return

        file_path = cpp_view.file_name()
        if not file_path.endswith('.cpp'): return

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')
        if not os.path.exists(test_file_path):
            sublime.status_message("未找到对应的测试文件: {}".format(test_file_path))
            return

        window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
        window.set_view_index(cpp_view, 0, 0)
        
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            html_content = generate_html(base_name, test_cases)
            ui_sheet = window.new_html_sheet("测试用例: {}".format(base_name), html_content)
            window.set_view_index(ui_sheet, 1, 0)
            ui_views[cpp_view.id()] = ui_sheet.id()
            window.focus_view(cpp_view)
        except Exception as e:
            sublime.error_message("加载或渲染测试用例失败: {}".format(e))
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

class CphUiCleanupListener(sublime_plugin.EventListener):
    """当关闭文件时，进行联动关闭和布局恢复"""
    def on_pre_close(self, sheet):
        closed_id = sheet.id()
        if closed_id in ui_views:
            window = sheet.window();
            if not window: return
            ui_sheet_id = ui_views.get(closed_id)
            del ui_views[closed_id]
            ui_sheet = find_sheet_by_id(window, ui_sheet_id)
            if ui_sheet:
                ui_sheet.settings().set('is_closing_by_plugin', True)
                ui_sheet.close()
            if not any(s.id() in ui_views.values() for s in window.sheets()):
                window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
        elif closed_id in ui_views.values():
            if sheet.settings().get('is_closing_by_plugin'): return
            cpp_id_to_delete = None
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == closed_id: cpp_id_to_delete = cpp_id; break
            if cpp_id_to_delete is not None:
                if cpp_id_to_delete in ui_views:
                    del ui_views[cpp_id_to_delete]
            window = sheet.window()
            if window and not any(s.id() in ui_views.values() for s in window.sheets()):
                 window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

class CphRunSingleTestCommand(sublime_plugin.WindowCommand):
    """由 command_url 触发，在后台线程中运行单个测试"""
    def run(self, test_index):
        # 这里的 active_view 应该是 C++ 文件，因为我们的UI视图是只读的，焦点在 C++ 文件上
        cpp_view = self.window.active_view()
        # 如果因为某些原因焦点不在 C++ 文件上，我们通过 UI 视图反向查找
        if not cpp_view or not cpp_view.file_name() or not cpp_view.file_name().endswith('.cpp'):
             active_sheet = self.window.active_sheet()
             if active_sheet and active_sheet.id() in ui_views.values():
                 cpp_view = get_cpp_view_for_ui(self.window, active_sheet.id())

        if cpp_view and cpp_view.file_name():
            threading.Thread(target=run_test_in_thread, args=(cpp_view, test_index)).start()

class CphRunTestsCommand(sublime_plugin.TextCommand):
    """由快捷键(F8)触发，在后台线程中运行全部测试"""
    def run(self, edit):
        threading.Thread(target=run_test_in_thread, args=(self.view, -1)).start()

class TestRunner():
    """封装了完整的测试逻辑，以便在线程中运行"""
    def __init__(self, cpp_view):
        self.cpp_view = cpp_view
        self.window = cpp_view.window()
        self.file_path = cpp_view.file_name()
        self.base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        self.test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', self.base_name + '_test.txt')

    def update_ui(self, test_cases, results):
        """在主线程中安全地更新UI"""
        html = generate_html(self.base_name, test_cases, results)
        ui_sheet_id = ui_views.get(self.cpp_view.id())
        if ui_sheet_id:
            ui_sheet = find_sheet_by_id(self.window, ui_sheet_id)
            if ui_sheet:
                ui_sheet.set_contents(html)
    
    def compile_cpp(self):
        executable_path = os.path.splitext(self.file_path)[0]
        compile_command = ["clang++-18", "-std=c++17", self.file_path, "-o", executable_path]
        process = subprocess.Popen(compile_command, stderr=subprocess.PIPE)
        _, stderr_bytes = process.communicate()
        if process.returncode != 0:
            sublime.error_message("编译错误:\n" + stderr_bytes.decode('utf-8'))
            return None
        return executable_path

    def run_single_test(self, executable_path, test_input):
        run_command = ["stdbuf", "-oL", executable_path]
        process = subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_bytes, _ = process.communicate(input=test_input.encode('utf-8'))
        return stdout_bytes.decode('utf-8')

    def run_and_update(self, target_index=-1):
        self.cpp_view.run_command("save")
        try:
            with open(self.test_file_path, 'r') as f:
                test_cases = json.load(f)
        except Exception:
            sublime.error_message("读取测试文件失败")
            return

        executable_path = self.compile_cpp()
        if not executable_path: return

        results = {}
        indices_to_run = range(len(test_cases)) if target_index == -1 else [target_index]

        for i in indices_to_run:
            results[i] = {'state': 'running'}
            sublime.set_timeout(lambda: self.update_ui(test_cases, results), 0)
            
            start_time = time.time()
            actual_output = self.run_single_test(executable_path, test_cases[i]['test'])
            end_time = time.time()
            
            cleaned_output = actual_output.strip().replace('\r\n', '\n')
            
            is_correct = False
            for answer in test_cases[i]['correct_answers']:
                cleaned_answer = answer.strip().replace('\r\n', '\n')
                if cleaned_output == cleaned_answer:
                    is_correct = True
                    break
            
            run_time_ms = int((end_time - start_time) * 1000)
            if is_correct:
                results[i] = {'state': 'passed', 'time': run_time_ms}
            else:
                results[i] = {'state': 'failed', 'time': run_time_ms, 'output': actual_output}
            
            sublime.set_timeout(lambda i=i: self.update_ui(test_cases, {i: results[i]}), 0)