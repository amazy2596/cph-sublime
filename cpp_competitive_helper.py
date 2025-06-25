# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 6.1 - [最终架构] 回归稳定实现：new_file + 辅助TextCommand
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json
import cgi

# 全局变量来追踪 UI 视图: { 'cpp_view_id': ui_view_id }
ui_views = {}

def find_view_by_id(window, view_id):
    """根据 id 寻找 view"""
    for view in window.views():
        if view.id() == view_id:
            return view
    return None

class CphToggleUiCommand(sublime_plugin.WindowCommand):
    """主命令：用于“打开”或“关闭”右侧的测试用例 UI 面板。"""
    def run(self):
        window = self.window
        cpp_view = window.active_view()
        if not cpp_view or not cpp_view.file_name():
            return

        ui_view_id = ui_views.get(cpp_view.id())
        
        # --- 情况一：UI 已打开，现在需要关闭它 ---
        if ui_view_id:
            ui_view = find_view_by_id(window, ui_view_id)
            if ui_view and ui_view.is_valid():
                ui_view.set_scratch(False)
                window.focus_view(ui_view)
                window.run_command("close_file")
            # on_pre_close 会处理字典清理和布局恢复
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
        # 将视图的语法设置为HTML，以获得高亮效果
        ui_view.assign_syntax("Packages/HTML/HTML.sublime-syntax")
        
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            
            # 这里只生成纯文本内容，由HTML语法高亮来美化
            content = "\n\n".format(cgi.escape(base_name))
            for i, case in enumerate(test_cases):
                content += "\n".format(i + 1)
                content += "Input:\n---\n{}\n---\n".format(case.get('test', 'N/A'))
                content += "Expected Output:\n---\n{}\n---\n\n".format("\n".join(case.get('correct_answers', [])))
            
            ui_view.run_command('_cph_update_view_content', {'content': content})
            window.focus_view(cpp_view)
        except Exception as e:
            sublime.error_message("加载测试用例失败: {}".format(e))
            window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
            if ui_view and ui_view.is_valid(): ui_view.close()

class _CphUpdateViewContentCommand(sublime_plugin.TextCommand):
    """一个内部使用的辅助命令，专门用于安全地修改视图内容。"""
    def run(self, edit, content=''):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, content)
        self.view.set_read_only(True)

class CphUiCleanupListener(sublime_plugin.EventListener):
    """当关闭文件时，进行联动关闭和布局恢复"""
    def on_pre_close(self, view):
        view_id = view.id()
        if view_id in ui_views:
            window = view.window()
            if not window: return
            ui_view_id = ui_views.get(view_id)
            del ui_views[view_id]
            ui_view = find_view_by_id(window, ui_view_id)
            if ui_view:
                ui_view.set_scratch(False)
                window.focus_view(ui_view)
                window.run_command("close_file")
        elif view_id in ui_views.values():
            cpp_id_to_delete = None
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == view_id:
                    cpp_id_to_delete = cpp_id
                    break
            if cpp_id_to_delete is not None:
                if cpp_id_to_delete in ui_views:
                    del ui_views[cpp_id_to_delete]
            window = view.window()
            if window and not any(v.id() in ui_views.values() for v in window.views()):
                 window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})

class CphRunTestsCommand(sublime_plugin.TextCommand):
    """负责运行测试的核心命令"""
    def run(self, edit):
        self.view.run_command("save")
        self.file_path = self.view.file_name()
        if not self.file_path or not self.file_path.endswith('.cpp'): return
            
        self.output_panel = self.view.window().create_output_panel("cph_output")
        self.view.window().run_command("show_panel", {"panel": "output.cph_output"})
        self.log("自动化测试开始... (已自动保存)")
        try:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')
            self.log("正在读取测试文件: {}".format(test_file_path))
            with open(test_file_path, 'r') as f:
                self.test_cases = json.load(f)
        except Exception as e:
            self.log("!!! 错误：读取或解析测试文件失败: {}".format(e))
            return
            
        executable_path = self.compile_cpp()
        if not executable_path: return

        # 决定是运行单个还是全部
        # 这里我们先只实现运行全部的功能
        self.run_all_tests(executable_path)

    def run_all_tests(self, executable_path):
        self.log("-" * 20)
        total_tests = len(self.test_cases)
        passed_tests = 0
        for i, test_case in enumerate(self.test_cases):
            self.log("运行测试点 #{}/{}:".format(i + 1, total_tests))
            # ... 后续逻辑和上一版完全一样 ...
            test_input = test_case.get('test', '')
            expected_answers = test_case.get('correct_answers', [])
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
        process = subprocess.Popen(compile_command, stderr=subprocess.PIPE)
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