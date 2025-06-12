import os
from tree_sitter import Language

# 确保build目录存在
os.makedirs('build', exist_ok=True)
# 解析器库输出路径（Windows下会自动生成my-languages.dll）
parser_library = os.path.join('build', 'my-languages.so')

# 编译五种语言的解析器（需确保对应文件夹存在）
Language.build_library(
    parser_library,
    [
        'tree-sitter-c',
        'tree-sitter-cpp',
        'tree-sitter-java',
        'tree-sitter-javascript',
        'tree-sitter-go'
    ]
)

print(f"解析器库已生成: {parser_library}")