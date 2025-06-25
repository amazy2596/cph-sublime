# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 4.0 - [重构] 废除 EventListener，改为手动开关式 UI
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

# 全局变量来追踪 UI 视图: { 'cpp_view_id': ui_view_id }
ui_views = {}

class CphToggleUiCommand(sublime_plugin.TextCommand):
    """
    主命令：用于“打开”或“关闭”右侧的测试用例 UI 面板。
    """
    def run(self, edit):
        window = self.view.window()
        cpp_view = self.view
        
        # 检查是否已为当前 CPP 文件打开了 UI
        ui_view_id = ui_views.get(cpp_view.id())
        
        # --- 情况一：UI 已打开，现在需要关闭它 ---
        if ui_view_id:
            ui_view = self.find_view_by_id(window, ui_view_id)
            if ui_view and ui_view.is_valid():
                # 先关闭视图
                ui_view.set_scratch(False)
                window.focus_view(ui_view)
                window.run_command("close_file")
            
            # 从追踪字典中移除
            del ui_views[cpp_view.id()]
            
            # 恢复单栏布局
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
            window.focus_view(cpp_view) # 将焦点还给 C++ 文件
            return

        # --- 情况二：UI 未打开，现在需要创建它 ---
        file_path = cpp_view.file_name()
        if not file_path or not file_path.endswith('.cpp'):
            return

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')

        if not os.path.exists(test_file_path):
            sublime.status_message("未找到对应的测试文件: {}".format(test_file_path))
            return

        # 设置两栏布局
        window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
        window.set_view_index(cpp_view, 0, 0)
        
        # 创建新视图
        ui_view = window.new_file()
        window.set_view_index(ui_view, 1, 0)
        ui_views[cpp_view.id()] = ui_view.id()
        ui_view.set_name("测试用例: {}".format(base_name))
        ui_view.set_scratch(True)
        
        # 加载并渲染内容
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            
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
            
            # 调用内部命令来更新视图内容
            ui_view.run_command('_cph_update_view_content', {'content': content})
            ui_view.set_read_only(True)
            window.focus_view(cpp_view) # 将焦点还给 C++ 文件

        except Exception as e:
            ui_view.run_command('_cph_update_view_content', {'content': "加载测试用例失败: {}".format(e)})
    
    def find_view_by_id(self, window, view_id):
        for view in window.views():
            if view.id() == view_id:
                return view
        return None

class _CphUpdateViewContentCommand(sublime_plugin.TextCommand):
    """
    一个内部使用的辅助命令，专门用于安全地修改视图内容。
    不能从外部直接调用。
    """
    def run(self, edit, content=''):
        self.view.set_read_only(False)
        self.view.replace(edit, sublime.Region(0, self.view.size()), content)
        self.view.set_read_only(True)

# CppHelperRunTestsCommand 保持不变，但我们改个名以统一风格
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