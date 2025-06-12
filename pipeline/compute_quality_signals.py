from base import quality_signals_registry
from document import QSCodeDocument

from collections import defaultdict
import json
import traceback
import time
import signal
import platform
from threading import Timer

# used for registration of all the quality signals
import quality_signals

# 新增
from tree_sitter import Language, Parser
import os
from pathlib import Path  # 新增导入

# 计算项目根路径（正确定位到 opc_data_filtering/opc_data_filtering）
current_file = os.path.abspath(__file__)
# 从 pipeline 目录向上两层到达项目根目录
ROOT_PATH = os.path.join(os.path.dirname(current_file), '..')


prefix2program = {
    'qsc_codecpp_': 'cpp',
    'qsc_codecsharp_': 'csharp',
    'qsc_codec_': 'c',
    'qsc_codego_': 'go',
    'qsc_codehtml_': 'html',
    'qsc_codejava_': 'java',
    'qsc_codejavascript_': 'javascript',
    'qsc_codepython_': 'python'
}

# 解析器库路径（位于项目根目录的 build 文件夹）
PARSER_LIBRARY = os.path.join(ROOT_PATH, 'build', 'my-languages.so')


def timed_out(signum, frame):
    raise TimeoutError("timeout")


class ComputeCodeQualitySignal():
    def __init__(self):
        self.code_instances = defaultdict(dict)
        self.specific_instances = defaultdict(dict)
        self.text_instances = defaultdict(dict)
        self.err_truncated_num = 10000 # used for truncating recorded error information

        # 新增：初始化 tree-sitter 解析器
        self._init_tree_sitter_parsers()

        for filter_name, filter in quality_signals_registry['codedocument'].items():
            # natural language filters
            if filter_name.startswith('qsc_doc_'):
                self.text_instances[filter_name] = filter()
            # general code filters
            elif filter_name.startswith('qsc_code_'):
                self.code_instances[filter_name] = filter()
            # language-specific code filters
            for prefix, program_lang in prefix2program.items():
                if filter_name.startswith(prefix):
                    self.specific_instances[program_lang][filter_name] = filter()

        
        self.default_time_out = 10
        self.filter_time = {} # {"quality signal name": timeout setting} You can set specific timeout for each filter
    
     # 新增：初始化 tree-sitter 解析器
    def _init_tree_sitter_parsers(self):
        # 确保 build 目录存在
        build_dir = os.path.dirname(PARSER_LIBRARY)
        os.makedirs(build_dir, exist_ok=True)

        # 检查 tree-sitter 语言仓库是否存在
        language_dirs = [
            os.path.join(ROOT_PATH, 'tree-sitter-c'),
            os.path.join(ROOT_PATH, 'tree-sitter-cpp'),
            os.path.join(ROOT_PATH, 'tree-sitter-java'),
            os.path.join(ROOT_PATH, 'tree-sitter-javascript'),
            os.path.join(ROOT_PATH, 'tree-sitter-go')
        ]
        
        # # 如果解析器库不存在，则编译它
        # if not os.path.exists(PARSER_LIBRARY):
        #     print("正在编译 tree-sitter 解析器库，这可能需要一些时间...")
        #     Language.build_library(
        #         PARSER_LIBRARY,
        #         language_dirs  # 使用完整路径列表
        #     )
        #     print("解析器库编译完成")
        
        # 加载各语言解析器
        self.language_parsers = {
            'c': Language(PARSER_LIBRARY, 'c'),
            'cpp': Language(PARSER_LIBRARY, 'cpp'),
            'java': Language(PARSER_LIBRARY, 'java'),
            'javascript': Language(PARSER_LIBRARY, 'javascript'),
            'go': Language(PARSER_LIBRARY, 'go'),
            # 可以根据需要添加更多语言
        }
        
        # 为每种语言创建解析器
        self.parsers = {
            lang: Parser() for lang in self.language_parsers
        }
        for lang, parser in self.parsers.items():
            parser.set_language(self.language_parsers[lang])
    
    # 新增：检查代码语法
    def check_syntax(self, text, program_lang):
        if program_lang not in self.parsers:
            return True  # 不支持的语言视为语法正确（或根据需求处理）
        
        try:
            # 解析代码
            tree = self.parsers[program_lang].parse(text.encode('utf-8'))
            # 判断是否有语法错误
            return not tree.root_node.has_error
        except Exception as e:
            print(f"语法检查出错: {program_lang}, 错误: {str(e)}")
            return False

    def truncate_err_string(self, err_string:str):
        if self.err_truncated_num > 2000:
            return err_string[:self.err_truncated_num-1005] + "\n...\n" + err_string[-1000:]
        else:
            return err_string[:self.err_truncated_num]

    def get_timeout(self, name:str):
        return self.filter_time.get(name, self.default_time_out)

    def get_final_result(self, result, err_msg, time_map):
        final_result = {
            'quality_signal': json.dumps(result)
        }
        final_result['pre_hit'] = '0'
        if len(err_msg) != 0:
            final_result['err_msg'] = json.dumps(err_msg)
        if len(time_map) != 0:
            final_result['time_map'] = json.dumps(time_map)

        return final_result

    # # compute a quality signal
    # def compute_filters(self, document:QSCodeDocument, instances, result, time_map, err_msg):
    #     try:
    #         for qname, filter in instances.items():
    #             start = time.time()
                
    #             # enable the timeout signal for each filter
    #             signal.setitimer(signal.ITIMER_REAL, self.get_timeout(qname), 0)

    #             ret = filter(document)

    #             # disable the timeout signal
    #             signal.setitimer(signal.ITIMER_REAL, 0)
                
    #             score = ret[0][2]

    #             result[qname] = score
    #             filter_time = time.time() - start
    #             time_map[qname] = round(filter_time, 8)

    #     except TimeoutError:
    #         result[qname] = None
    #         err_msg[qname] = f"[WARN] {qname} time out error, time set: {self.default_time_out}"
    #         print(err_msg[qname], flush=True)

    #     except Exception as e:
    #         result[qname] = None
    #         error_string = traceback.format_exc()
    #         if len(error_string) > self.err_truncated_num:
    #             error_string = self.truncate_err_string(error_string)
    #         err_msg[qname] = f"[WARN] qname: {qname}, Exception: {error_string}"
    #         print(err_msg[qname], flush=True)
        
    #     return result, time_map, err_msg

    # compute a quality signal
    def compute_filters(self, document:QSCodeDocument, instances, result, time_map, err_msg):
        for qname, filter in instances.items():
            start = time.time()
            ret = None
            
            # 根据操作系统类型选择不同的超时实现
            if platform.system() == "Windows":
                # Windows 系统使用线程定时器实现超时
                timeout = self.get_timeout(qname)
                # 创建一个标志变量用于检查是否超时
                timed_out = False
                
                # 定义超时处理函数
                def set_timed_out():
                    nonlocal timed_out
                    timed_out = True
                
                # 创建定时器
                timer = Timer(timeout, set_timed_out)
                timer.start()
                
                try:
                    # 执行过滤函数
                    ret = filter(document)
                    # 如果在超时前完成，取消定时器
                    if not timed_out:
                        timer.cancel()
                    else:
                        # 如果超时，抛出异常
                        raise TimeoutError(f"Timeout after {timeout} seconds")
                except Exception as e:
                    # 处理异常
                    if isinstance(e, TimeoutError):
                        result[qname] = None
                        err_msg[qname] = f"[WARN] {qname} time out error, time set: {timeout}"
                        print(err_msg[qname], flush=True)
                    else:
                        result[qname] = None
                        error_string = traceback.format_exc()
                        if len(error_string) > self.err_truncated_num:
                            error_string = self.truncate_err_string(error_string)
                        err_msg[qname] = f"[WARN] qname: {qname}, Exception: {error_string}"
                        print(err_msg[qname], flush=True)
            else:
                # Unix/Linux 系统使用原有的信号机制
                try:
                    # enable the timeout signal for each filter
                    signal.signal(signal.SIGALRM, timed_out)
                    signal.setitimer(signal.ITIMER_REAL, self.get_timeout(qname), 0)

                    ret = filter(document)

                    # disable the timeout signal
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    
                    score = ret[0][2]
                    result[qname] = score
                except TimeoutError:
                    result[qname] = None
                    err_msg[qname] = f"[WARN] {qname} time out error, time set: {self.get_timeout(qname)}"
                    print(err_msg[qname], flush=True)
                except Exception as e:
                    result[qname] = None
                    error_string = traceback.format_exc()
                    if len(error_string) > self.err_truncated_num:
                        error_string = self.truncate_err_string(error_string)
                    err_msg[qname] = f"[WARN] qname: {qname}, Exception: {error_string}"
                    print(err_msg[qname], flush=True)
            
            # 计算并记录处理时间
            filter_time = time.time() - start
            time_map[qname] = round(filter_time, 8)
        
        return result, time_map, err_msg


    # compute quality signals for a document
    def compute_qs(self, text:str, filename:str, lang:str, ext:str, file_size_in_byte:int, program_lang:str, doc_type:str):

        # signal.signal(signal.SIGALRM, timed_out)
        # 兼容 Windows 的超时处理
        # if os.name == 'nt':  # Windows 系统
        #     # Windows 不支持 SIGALRM，使用其他方式处理超时（或暂时禁用）
        #     print("警告: Windows 系统不支持超时信号，将禁用超时功能")
        # else:  # Unix/Linux 系统
        #     signal.signal(signal.SIGALRM, timed_out)
        #     signal.setitimer(signal.ITIMER_REAL, self.get_timeout("default"), 0)


        document = QSCodeDocument(content=text,
                                filename=filename,
                                language=lang,
                                extension=ext,
                                file_size_in_byte=file_size_in_byte,
                                program_lang=program_lang,
                                doc_type=doc_type
                                )
                    
        result = {}
        err_msg = {}
        time_map = {}
        
        # if doc_type is 'unknown' then do not process this document
        if doc_type == 'unknown': 
            pass
        
        # if doc_type is 'code' or 'data' then use general code filters and language-specific code filters
        elif doc_type == 'code' or doc_type == 'data':
            # general code filters
            result, time_map, err_msg = self.compute_filters(document, self.code_instances, result, time_map, err_msg)
            # language-specific code filters
            result, time_map, err_msg = self.compute_filters(document, self.specific_instances[program_lang], result, time_map, err_msg)

            # 新增：添加语法检查结果到质量信号
            if program_lang in self.parsers:
                syntax_valid = self.check_syntax(text, program_lang)
                result[f'qsc_syntax_{program_lang}'] = 1 if syntax_valid else 0
                if not syntax_valid:
                    err_msg[f'syntax_{program_lang}'] = f"[ERROR] {program_lang} 语法错误"

        # if doc_type is 'text' then use natural language filters
        elif doc_type == 'text':
            # natural language filters
            result, time_map, err_msg = self.compute_filters(document, self.text_instances, result, time_map, err_msg)

        final_result = self.get_final_result(result, err_msg, time_map)
        
        return json.dumps(final_result,ensure_ascii=False)

    # processing entrance
    def evaluate(self, text:str, filename:str, lang:str, ext:str, file_size_in_byte:int, 
                 program_lang:str, doc_type:str):

        try:
            result = self.compute_qs(text, filename, lang, ext, 
            file_size_in_byte, program_lang, doc_type)

            return result
        except Exception as e:
            error_string = traceback.format_exc()
            if len(error_string) > self.err_truncated_num:
                error_string = self.truncate_err_string(error_string)
            final_result = {
                'err_msg': json.dumps({
                    'total_crush': error_string
                })
            }
            return json.dumps(final_result,ensure_ascii=False)
        
