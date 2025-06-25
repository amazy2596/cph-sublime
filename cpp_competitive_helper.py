# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 3.1 - [BUG修复] 修正关闭文件时因递归调用导致的 KeyError
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

# 全局变量来追踪我们的 UI 视图: { 'cpp_view_id': ui_view_id }
ui_views = {}

class CppHelperEventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        file_path = view.file_name()
        if not file_path or not file_path.endswith('.cpp'):
            return
        view.run_command('cpp_helper_show_ui')

    # --- 这是修正后的 on_pre_close 函数 ---
    def on_pre_close(self, view):
        view_id = view.id()

        # 情况一：如果关闭的是一个有对应 UI 视图的 C++ 文件
        if view_id in ui_views:
            ui_view = sublime.View(ui_views[view_id])
            
            # 关键：先从我们的追踪字典中删除记录
            del ui_views[view_id]
            
            # 然后再安全地关闭 UI 视图（此时即使触发递归，也不会有问题）
            if ui_view and ui_view.is_valid():
                ui_view.set_scratch(False)
                ui_view.window().focus_view(ui_view)
                ui_view.window().run_command("close_file")

        # 情况二：如果关闭的是一个 UI 视图本身
        # (因为上一步已经处理了联动关闭，这里主要处理用户手动关闭UI视图的情况)
        elif view_id in ui_views.values():
            cpp_id_to_delete = None
            # 遍历字典找到这个 UI 视图属于哪个 C++ 文件
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == view_id:
                    cpp_id_to_delete = cpp_id
                    break
            
            # 如果找到了，就从字典中删除
            if cpp_id_to_delete is not None and cpp_id_to_delete in ui_views:
                del ui_views[cpp_id_to_delete]

# ... CppHelperShowUiCommand 和 CppHelperRunTestsCommand 的代码和上一版完全一样 ...
# 为了方便您完整复制，下面将所有代码一并提供

class CppHelperShowUiCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        window = self.view.window()
        if not window: return
        file_path = self.view.file_name()
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')
        if not os.path.exists(test_file_path):
            if self.view.id() in ui_views:
                ui_view = sublime.View(ui_views[self.view.id()])
                if ui_view and ui_view.is_valid():
                    ui_view.set_scratch(False)
                    ui_view.window().focus_view(ui_view)
                    ui_view.window().run_command("close_file")
                del ui_views[self.view.id()]
            return
        if window.num_groups() != 2:
            layout = {"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]}
            window.set_layout(layout)
        window.set_view_index(self.view, 0, 0)
        window.focus_view(self.view)
        ui_view = None
        if self.view.id() in ui_views and sublime.View(ui_views[self.view.id()]).is_valid():
            ui_view = sublime.View(ui_views[self.view.id()])
            window.focus_view(ui_view)
        else:
            ui_view = window.new_file()
            ui_views[self.view.id()] = ui_view.id()
        window.set_view_index(ui_view, 1, 0)
        ui_view.set_name("测试用例: {}".format(base_name))
        ui_view.set_scratch(True)
        ui_view.set_read_only(True)
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            ui_view.run_command('select_all')
            ui_view.run_command('right_delete')
            content = "测试文件: {}\n".format(test_file_path)
            content += "=" * 40 + "\n\n"
            for i, case in enumerate(test_cases):
                content += "--- 测试点 #{} ---\n".format(i + 1)
                content += "输入 (Input):\n{}\n".format(case.get('test', 'N/A'))
                answers = case.get('correct_answers', [])
                content += "答案 (Answers):\n"
                for ans in answers:
                    content += "{}\n".format(ans)
                content += "\n"
            ui_view.run_command('append', {'characters': content})
        except Exception as e:
            ui_view.run_command('append', {'characters': "加载测试用例失败: {}".format(e)})

class CppHelperRunTestsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.run_command("save")
        self.file_path = self.view.file_name()
        if not self.file_path or not self.file_path.endswith('.cpp'):
            sublime.status_message("错误：请先在 C++ (.cpp) 文件中执行此命令")
            return
        self.output_panel = self.view.window().create_output_panel("cpp_helper_output")
        self.view.window().run_command("show_panel", {"panel": "output.cpp_helper_output"})
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
        process = subprocess.Popen(
            run_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout_bytes, _ = process.communicate(input=test_input.encode('utf-8'))
        return stdout_bytes.decode('utf-8')