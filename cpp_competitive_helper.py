# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 5.1 - [UI] 抽离 UI 到模板文件，实现静态视觉复刻
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json
import cgi

ui_views = {}

class CphToggleUiCommand(sublime_plugin.WindowCommand):
    def run(self):
        window = self.window
        cpp_view = window.active_view()
        if not cpp_view or not cpp_view.file_name():
            return

        ui_sheet_id = ui_views.get(cpp_view.id())
        
        if ui_sheet_id:
            ui_sheet = self.find_sheet_by_id(window, ui_sheet_id)
            if ui_sheet:
                ui_sheet.close()
            return

        file_path = cpp_view.file_name()
        if not file_path.endswith('.cpp'):
            return

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
            
            html_content = self.generate_html(base_name, test_cases)
            
            ui_sheet = window.new_html_sheet("测试用例: {}".format(base_name), html_content, group=1)
            ui_views[cpp_view.id()] = ui_sheet.id()
            window.focus_view(cpp_view)

        except Exception as e:
            sublime.error_message("加载或渲染测试用例失败: {}".format(e))
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
            
    def generate_html(self, problem_name, test_cases):
        try:
            # 从插件包中加载 HTML 模板
            template = sublime.load_resource("Packages/cph-sublime/ui_template.html")
        except IOError:
            return "错误：找不到 ui_template.html 文件！"

        test_cases_html = ""
        for i, case in enumerate(test_cases):
            test_input = cgi.escape(case.get('test', 'N/A'))
            answers_html = "<br>".join([cgi.escape(ans) for ans in case.get('correct_answers', [])])

            case_html = """
            <details open>
                <summary>
                    <span class="case-title">TC {}</span>
                    <div class="case-buttons">
                        <a href="run:{}" class="run-btn">▶</a>
                        <a href="delete:{}" class="del-btn">🗑</a>
                    </div>
                </summary>
                <div class="content-block">
                    <h4><span>Input:</span><a class="copy-btn" href="copy_in:{}">Copy</a></h4>
                    <pre>{}</pre>
                </div>
                <div class="content-block">
                    <h4><span>Expected Output:</span><a class="copy-btn" href="copy_out:{}">Copy</a></h4>
                    <pre>{}</pre>
                </div>
            </details>
            """.format(i + 1, i, i, i, test_input, i, answers_html)
            test_cases_html += case_html

        # 替换模板中的占位符
        final_html = template.replace("{problem_name}", cgi.escape(problem_name))
        final_html = final_html.replace("{test_cases_html}", test_cases_html)
        
        return final_html

    def find_sheet_by_id(self, window, sheet_id):
        for sheet in window.sheets():
            if sheet.id() == sheet_id:
                return sheet
        return None

class CphUiCleanupListener(sublime_plugin.EventListener):
    def on_pre_close(self, sheet):
        closed_id = sheet.id()
        if closed_id in ui_views:
            window = sheet.window();
            if not window: return
            ui_sheet_id = ui_views.get(closed_id)
            del ui_views[closed_id]
            ui_sheet = CphToggleUiCommand.find_sheet_by_id(CphToggleUiCommand, window, ui_sheet_id)
            if ui_sheet:
                ui_sheet.settings().set('is_closing_by_plugin', True)
                ui_sheet.close()
            if not any(s.id() in ui_views.values() for s in window.sheets()):
                window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
        elif closed_id in ui_views.values():
            if sheet.settings().get('is_closing_by_plugin'): return
            cpp_id_to_delete = None
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == closed_id:
                    cpp_id_to_delete = cpp_id
                    break
            if cpp_id_to_delete is not None:
                del ui_views[cpp_id_to_delete]
            window = sheet.window()
            if window and not any(s.id() in ui_views.values() for s in window.sheets()):
                window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

# CphRunTestsCommand 保持不变
class CphRunTestsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.run_command("save")
        self.file_path = self.view.file_name()
        if not self.file_path or not self.file_path.endswith('.cpp'):
            sublime.status_message("错误：请先在 C++ (.cpp) 文件中执行此命令")
            return
        self.output_panel = self.view.window().create_output_panel("cph_output")
        self.view.window().run_command("show_panel", {"panel": "output.cph_output"})
        self.log("自动化测试开始... (已自动保存)")
        try:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')
            self.log("正在读取测试文件: {}".format(test_file_path))
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
        except (IOError, OSError):
            self.log("!!! 错误：找不到或无法读取测试文件: {}".format(test_file_path))
            return
        except ValueError:
            self.log("!!! 错误：JSON 文件格式不正确，请检查。")
            return
        except Exception as e:
            self.log("!!! 错误：解析测试文件时发生未知问题: {}".format(e))
            return
        executable_path = self.compile_cpp()
        if not executable_path:
            return
        self.log("-" * 20)
        total_tests = len(test_cases)
        passed_tests = 0
        for i, test_case in enumerate(test_cases):
            self.log("运行测试点 #{}/{}:".format(i + 1, total_tests))
            if 'test' not in test_case or 'correct_answers' not in test_case:
                self.log("  结果: Invalid Case (JSON中缺少 'test' 或 'correct_answers' 字段)")
                continue
            test_input = test_case['test']
            expected_answers = test_case['correct_answers']
            actual_output = self.run_single_test(executable_path, test_input)
            cleaned_output = actual_output.strip().replace('\r\n', '\n')
            is_correct = False
            for answer in expected_answers:
                cleaned_answer = answer.strip().replace('\r\n', '\n')
                if cleaned_output == cleaned_answer:
                    is_correct = True
                    break
            if is_correct:
                self.log("  结果: Accepted (AC)")
                passed_tests += 1
            else:
                self.log("  结果: Wrong Answer (WA)")
                self.log("    - 期望输出 (之一):\n{}\n".format(expected_answers[0]))
                self.log("    - 你的输出:\n{}\n".format(actual_output))
        self.log("-" * 20)
        self.log("自动化测试结束。结果: {} / {} 通过。".format(passed_tests, total_tests))

    def log(self, message):
        self.output_panel.run_command("append", {"characters": message + "\n"})
        
    def compile_cpp(self):
        base_name = os.path.splitext(self.file_path)[0]
        executable_path = base_name
        compile_command = ["clang++-18", "-std=c++17", self.file_path, "-o", executable_path]
        self.log("正在编译: {}".format(' '.join(compile_command)))
        process = subprocess.Popen(compile_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr_bytes = process.communicate()
        if process.returncode != 0:
            self.log("!!! 编译错误 !!!")
            self.log(stderr_bytes.decode('utf-8'))
            return None
        self.log("编译成功, 可执行文件位于: {}".format(executable_path))
        return executable_path

    def run_single_test(self, executable_path, test_input):
        run_command = ["stdbuf", "-oL", executable_path]
        process = subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_bytes, _ = process.communicate(input=test_input.encode('utf-8'))
        return stdout_bytes.decode('utf-8')