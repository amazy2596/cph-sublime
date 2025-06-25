# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 7.1 - [测试] 将稳定的底部面板输出重定向到右侧视图
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json
import time

# 全局变量，用于追踪 cpp_view 和 output_view 的关系
# 格式: { 'cpp_view_id': output_view_object }
output_views = {}

class CphRunTestsCommand(sublime_plugin.TextCommand):
    """
    运行测试，但将所有日志输出重定向到右侧的一个新建视图中。
    """
    def run(self, edit):
        window = self.view.window()
        self.cpp_view = self.view

        # --- 核心改动：创建或找到右侧的输出视图 ---
        output_view = self.get_or_create_output_view(window)
        # 清空上一次的输出
        output_view.run_command('_cph_update_content', {'content': ''})

        # --- 后续逻辑和稳定版基本一致，只是 log 的目标变了 ---
        self.log("自动化测试开始... (右侧面板模式)")
        
        self.file_path = self.cpp_view.file_name()
        if not self.file_path or not self.file_path.endswith('.cpp'):
            self.log("错误：请在 C++ (.cpp) 文件中执行此命令")
            return

        try:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')
            self.log("正在读取测试文件: {}".format(test_file_path))
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
        except Exception as e:
            self.log("!!! 错误：读取或解析测试文件失败: {}".format(e))
            return
            
        executable_path = self.compile_cpp()
        if not executable_path:
            return

        self.run_all_tests(executable_path, test_cases)

    def get_or_create_output_view(self, window):
        output_view = output_views.get(self.cpp_view.id())
        
        # 如果找不到或者视图已经失效（被用户关闭了）
        if not output_view or not output_view.is_valid():
            # 设置两栏布局
            window.set_layout({"cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]})
            # 确保当前C++文件在左边
            window.set_view_index(self.cpp_view, 0, 0)
            
            # 在右边创建新视图
            output_view = window.new_file()
            window.set_view_index(output_view, 1, 0)
            
            output_view.set_name("测试输出")
            output_view.set_scratch(True) # 临时文件，关闭不提示保存
            output_view.settings().set('word_wrap', True)

            # 记录我们的新视图
            output_views[self.cpp_view.id()] = output_view
            
            # 将焦点还给 C++ 文件
            window.focus_view(self.cpp_view)

        return output_view

    def run_all_tests(self, executable_path, test_cases):
        self.log("-" * 20)
        # ... (这部分和 v7.0 完全一样)
        total_tests = len(test_cases)
        passed_tests = 0
        for i, test_case in enumerate(test_cases):
            self.log("运行测试点 #{}/{}:".format(i + 1, total_tests))
            test_input = test_case.get('test', '')
            expected_answers = test_case.get('correct_answers', [])
            start_time = time.time()
            actual_output = self.run_single_test(executable_path, test_input)
            end_time = time.time()
            run_time_ms = int((end_time - start_time) * 1000)
            cleaned_output = actual_output.strip().replace('\r\n', '\n')
            is_correct = False
            for answer in expected_answers:
                cleaned_answer = answer.strip().replace('\r\n', '\n')
                if cleaned_output == cleaned_answer:
                    is_correct = True
                    break
            if is_correct:
                self.log("  结果: Accepted (AC)  ({}ms)".format(run_time_ms))
                passed_tests += 1
            else:
                self.log("  结果: Wrong Answer (WA)  ({}ms)".format(run_time_ms))
                self.log("    - 期望输出 (之一):\n{}".format(expected_answers[0]))
                self.log("    - 你的输出:\n{}".format(actual_output))
        self.log("-" * 20)
        self.log("自动化测试结束。结果: {} / {} 通过。".format(passed_tests, total_tests))

    def log(self, message):
        """将日志写入到右侧的视图中"""
        output_view = output_views.get(self.cpp_view.id())
        if output_view and output_view.is_valid():
            output_view.run_command('_cph_update_content', {'content': message + "\n", 'append': True})

    def compile_cpp(self):
        # ... (这部分和 v7.0 完全一样)
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
        # ... (这部分和 v7.0 完全一样)
        run_command = ["stdbuf", "-oL", executable_path]
        process = subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_bytes, _ = process.communicate(input=test_input.encode('utf-8'))
        return stdout_bytes.decode('utf-8')

class _CphUpdateContentCommand(sublime_plugin.TextCommand):
    """
    一个内部使用的辅助命令，用于安全地向视图写入或追加内容。
    """
    def run(self, edit, content, append=False):
        self.view.set_read_only(False)
        if append:
            self.view.insert(edit, self.view.size(), content)
        else: # 替换全部内容
            self.view.erase(edit, sublime.Region(0, self.view.size()))
            self.view.insert(edit, 0, content)
        self.view.set_read_only(True)