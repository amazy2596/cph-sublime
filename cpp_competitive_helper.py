# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
#
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os

class CppHelperTestWslCommand(sublime_plugin.TextCommand):
    """
    这个命令用于测试 Sublime Text 是否能成功调用同一个 Linux 环境中的其他程序。
    它会执行 `uname -a` 并将结果输出到面板。
    此版本完全兼容 Python 3.3。
    """
    def run(self, edit):
        # 要在 Linux 中执行的命令
        command_to_run = "uname -a"
        full_command = command_to_run.split()

        # 创建一个新的输出面板来显示结果
        output_panel = self.view.window().create_output_panel("cpp_helper_output")
        self.view.window().run_command("show_panel", {"panel": "output.cpp_helper_output"})
        
        # 使用 .format() 替换 f-string
        output_panel.run_command("append", {"characters": "正在尝试执行命令: {}\n\n".format(' '.join(full_command))})

        try:
            # 使用 Python 3.3 兼容的 subprocess.Popen
            # Popen 是非阻塞的，我们需要调用 .communicate() 来等待它完成并获取输出
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout_bytes, stderr_bytes = process.communicate()

            # Popen 返回的是字节串(bytes), 我们需要手动解码成字符串(string)
            stdout = stdout_bytes.decode('utf-8')
            stderr = stderr_bytes.decode('utf-8')

            # 将命令的输出显示到面板
            output_panel.run_command("append", {"characters": "--- Linux 返回的输出 ---\n"})
            output_panel.run_command("append", {"characters": stdout})
            output_panel.run_command("append", {"characters": "\n"})

            # 如果有错误信息，也显示出来
            if stderr:
                output_panel.run_command("append", {"characters": "--- 返回的错误信息 ---\n"})
                output_panel.run_command("append", {"characters": stderr})

        except FileNotFoundError:
            # 使用 .format() 替换 f-string
            error_message = "错误: 命令 '{}' 未找到。\n请确保它已安装并在您的 PATH 环境变量中。\n".format(full_command[0])
            output_panel.run_command("append", {"characters": error_message})
        except Exception as e:
            # 使用 .format() 替换 f-string
            error_message = "执行时发生未知错误: {}\n".format(e)
            output_panel.run_command("append", {"characters": error_message})