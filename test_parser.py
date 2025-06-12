import os
from tree_sitter import Language, Parser

# 加载编译好的解析器库
LANGUAGE_LIB = os.path.join('build', 'my-languages.so')
if not os.path.exists(LANGUAGE_LIB):
    raise FileNotFoundError(f"解析器库不存在: {LANGUAGE_LIB}")

# 初始化解析器（包含C）
java_language = Language(LANGUAGE_LIB, 'java')
cpp_language = Language(LANGUAGE_LIB, 'cpp')
c_language = Language(LANGUAGE_LIB, 'c')  # 使用 C 语言解析器
javascript_language = Language(LANGUAGE_LIB, 'javascript')
go_language = Language(LANGUAGE_LIB, 'go')

# 测试代码（包含C而非Rust）
test_cases = [
    ("java", "public class Test { public static void main(String[] args) { } }", False),
    ("java", "public class Test { public static void main(String[] args) {", True),
    ("cpp", "#include <iostream>\nint main() { std::cout << \"Hello\"; return 0; }", False),
    ("c", "#include <stdio.h>\nint main() { printf(\"Hello\"); return 0; }", False),  # C 正确代码
    ("c", "#include <stdio.h>\nint main() { printf(\"Hello\");", True),     # C 错误代码（缺少闭合括号）
    ("javascript", "function add(a, b) { return a + b; }", False),
    ("go", "package main\nfunc main() {}", False)
]

# 执行测试
parser = Parser()
for lang, code, should_have_error in test_cases:
    # 设置语言解析器
    if lang == 'java':
        parser.set_language(java_language)
    elif lang == 'cpp':
        parser.set_language(cpp_language)
    elif lang == 'c':
        parser.set_language(c_language)  # 使用 C 语言解析器
    elif lang == 'javascript':
        parser.set_language(javascript_language)
    elif lang == 'go':
        parser.set_language(go_language)
    
    # 解析代码
    tree = parser.parse(code.encode('utf-8'))
    has_error = tree.root_node.has_error
    
    # 验证结果
    result = "通过" if (has_error == should_have_error) else "失败"
    error_status = "有错误" if has_error else "无错误"
    expected = "有错误" if should_have_error else "无错误"
    
    print(f"{lang}测试: {result}")
    print(f"  代码: {code[:30]}...")
    print(f"  检测结果: {error_status}")
    print(f"  预期结果: {expected}")
    print("-" * 50)
