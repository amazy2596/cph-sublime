# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 2.3 - [功能增强] 运行前自动保存当前文件
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

class CppHelperTestWslCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.status_message("F1 是运行测试命令。")

class CppHelperRunTestsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        # --- 新增功能：运行前自动保存 ---
        self.view.run_command("save")
        
        # --- 后续逻辑完全不变 ---
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