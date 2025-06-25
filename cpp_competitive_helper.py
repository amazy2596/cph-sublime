# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 4.2 - [架构修复] 使用 WindowCommand 和 TextCommand 的正确组合，解决 TypeError 崩溃问题
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

# 全局变量来追踪 UI 视图: { 'cpp_view_id': ui_view_id }
ui_views = {}

# --- 主命令改为 WindowCommand，因为它操作的是窗口布局和多视图 ---
class CphToggleUiCommand(sublime_plugin.WindowCommand):
    def run(self):
        window = self.window
        # WindowCommand 没有直接的 self.view，我们需要获取当前活动的视图
        cpp_view = window.active_view()
        
        if not cpp_view or not cpp_view.file_name():
            return

        ui_view_id = ui_views.get(cpp_view.id())
        
        # --- 情况一：UI 已打开，现在需要关闭它 ---
        if ui_view_id:
            ui_view = self.find_view_by_id(window, ui_view_id)
            if ui_view and ui_view.is_valid():
                ui_view.set_scratch(False)
                window.focus_view(ui_view)
                window.run_command("close_file")
            
            if cpp_view.id() in ui_views:
                del ui_views[cpp_view.id()]
            
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
            window.focus_view(cpp_view)
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

        window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
        window.set_view_index(cpp_view, 0, 0)
        
        ui_view = window.new_file()
        window.set_view_index(ui_view, 1, 0)
        ui_views[cpp_view.id()] = ui_view.id()
        ui_view.set_name("测试用例: {}".format(base_name))
        ui_view.set_scratch(True)
        
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
            
            # 核心改动：调用一个 TextCommand 来安全地写入内容
            ui_view.run_command('_cph_update_view_content', {'content': content})

        except Exception as e:
            error_content = "加载测试用例失败: {}".format(e)
            ui_view.run_command('_cph_update_view_content', {'content': error_content})
        
        # 将焦点还给 C++ 文件
        window.focus_view(cpp_view)

    def find_view_by_id(self, window, view_id):
        for view in window.views():
            if view.id() == view_id:
                return view
        return None

# --- 重新引入这个内部辅助命令，它是一个 TextCommand ---
class _CphUpdateViewContentCommand(sublime_plugin.TextCommand):
    def run(self, edit, content=''):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, content)
        self.view.set_read_only(True)

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
    
# (请将这个类追加到文件的末尾)
class CphMinimalTestCommand(sublime_plugin.WindowCommand):
    """
    一个极简的诊断命令，只做三件事：
    1. 设置两栏布局
    2. 在右侧创建一个新视图
    3. 尝试向新视图写入 "Hello, World!"
    """
    def run(self):
        window = self.window
        
        # 1. 设置布局
        if window.num_groups() != 2:
            window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
        
        # 2. 创建新视图
        new_view = window.new_file()
        window.set_view_index(new_view, 1, 0)
        new_view.set_name("诊断测试视图")

        # 3. 尝试写入内容
        # 我们使用 set_timeout 延迟执行，这有时能解决 API 调用的时序问题
        # 这是一个非常常见的 Sublime 插件开发技巧
        content_to_write = "Hello, World! 如果您能看到这句话，说明核心写入功能是正常的。"
        sublime.set_timeout(lambda: new_view.run_command('_cph_update_view_content', {'content': content_to_write}), 100)