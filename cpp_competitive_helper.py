# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 5.0 - [最终修复] 使用 new_html_sheet API 实现 HTML UI
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

# 全局变量来追踪 UI 视图: { 'cpp_view_id': html_sheet_id }
ui_views = {}

class CphToggleUiCommand(sublime_plugin.WindowCommand):
    """
    主命令：使用正确的 new_html_sheet API 打开或关闭右侧的 HTML 测试用例面板。
    """
    def run(self):
        window = self.window
        cpp_view = window.active_view()
        
        if not cpp_view or not cpp_view.file_name():
            return

        ui_sheet_id = ui_views.get(cpp_view.id())
        
        # --- 情况一：UI 已打开，现在需要关闭它 ---
        if ui_sheet_id:
            ui_sheet = self.find_sheet_by_id(window, ui_sheet_id)
            if ui_sheet:
                ui_sheet.close() # 使用 sheet.close() 是最安全的关闭方法
            
            # on_pre_close 事件会自动处理字典清理和布局恢复
            return

        # --- 情况二：UI 未打开，现在需要创建它 ---
        file_path = cpp_view.file_name()
        if not file_path.endswith('.cpp'):
            return

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')

        if not os.path.exists(test_file_path):
            sublime.status_message("未找到对应的测试文件: {}".format(test_file_path))
            return

        # 设置两栏布局
        window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
        window.set_view_index(cpp_view, 0, 0)
        
        # 加载并生成 HTML 内容
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            
            # 使用 HTML 格式化内容
            html_content = self.generate_html(test_cases)
            
            # 核心API：直接创建 HTML Sheet
            ui_sheet = window.new_html_sheet("测试用例: {}".format(base_name), html_content, group=1)
            
            # 记录 C++ 视图和 UI Sheet 的对应关系
            ui_views[cpp_view.id()] = ui_sheet.id()
            window.focus_view(cpp_view)

        except Exception as e:
            sublime.error_message("加载测试用例失败: {}".format(e))
            # 如果失败了，恢复单栏布局
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
            
    def generate_html(self, test_cases):
        # 使用简单的 HTML 和 CSS 来美化界面
        # 注意：Sublime 的 minihtml 支持有限的 CSS
        styles = """
        <style>
            body { padding: 10px; font-family: sans-serif; }
            h3 { color: #4e8ed6; border-bottom: 1px solid #444; padding-bottom: 5px; margin-top: 20px;}
            h4 { color: #999; }
            pre { background-color: #222; padding: 10px; border-radius: 5px; font-family: monospace; }
        </style>
        """
        body = ""
        for i, case in enumerate(test_cases):
            test_input = case.get('test', 'N/A').replace('\n', '<br>')
            
            answers_html = ""
            answers = case.get('correct_answers', [])
            for ans in answers:
                answers_html += ans.replace('\n', '<br>') + "<br>"

            body += "<h3>测试点 #{}</h3>".format(i + 1)
            body += "<h4>输入 (Input):</h4><pre>{}</pre>".format(test_input)
            body += "<h4>答案 (Answers):</h4><pre>{}</pre>".format(answers_html)

        return styles + body

    def find_sheet_by_id(self, window, sheet_id):
        for sheet in window.sheets():
            if sheet.id() == sheet_id:
                return sheet
        return None

# --- 这个监听器现在只负责清理工作 ---
class CphUiCleanupListener(sublime_plugin.EventListener):
    def on_pre_close(self, view_or_sheet):
        # view_or_sheet 可以是 View 也可以是 Sheet
        closed_id = view_or_sheet.id()

        # 情况一：如果关闭的是一个 C++ 文件
        if closed_id in ui_views:
            window = view_or_sheet.window()
            if not window: return
            
            ui_sheet_id = ui_views.get(closed_id)
            ui_sheet = CphToggleUiCommand.find_sheet_by_id(CphToggleUiCommand, window, ui_sheet_id)
            
            if ui_sheet:
                # 标记正在被插件关闭，防止触发自己的 on_pre_close 时再次进入逻辑
                ui_sheet.settings().set('is_closing_by_plugin', True)
                ui_sheet.close()
            
            del ui_views[closed_id]
            # 如果没有其他 UI 了，恢复布局
            if not ui_views:
                window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

        # 情况二：如果关闭的是 UI Sheet
        elif closed_id in ui_views.values():
            if view_or_sheet.settings().get('is_closing_by_plugin'):
                return # 如果是插件自己关的，就不用再处理了
            
            cpp_id_to_delete = None
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == closed_id:
                    cpp_id_to_delete = cpp_id
                    break
            
            if cpp_id_to_delete is not None:
                del ui_views[cpp_id_to_delete]
            
            # 如果没有其他 UI 了，恢复布局
            if not ui_views:
                window = view_or_sheet.window()
                if window:
                     window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

# --- 测试运行命令保持不变 ---
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