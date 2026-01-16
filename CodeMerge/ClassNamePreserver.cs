using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Linq;

namespace CodeMerge
{
    /// <summary>
    /// 类型声明信息
    /// </summary>
    public class TypeDeclaration
    {
        public string FullMatch;           // 完整匹配文本
        public string TypeKeyword;         // class/struct/interface/enum
        public string TypeName;            // 类型名称
        public string NewTypeName;         // 新类型名称（用于替换）
        public string Modifiers;           // 修饰符 (public, abstract, etc.)
        public string GenericParams;       // 泛型参数
        public string BaseTypes;           // 继承的基类/接口
        public int LineNumber;             // 行号
        public int StartIndex;             // 在文本中的起始位置
        public int Length;                 // 匹配长度
        
        public override string ToString()
        {
            return $"[{TypeKeyword}] {TypeName} at line {LineNumber}";
        }
    }

    /// <summary>
    /// 类名保留选项
    /// </summary>
    [Flags]
    public enum PreserveOptions
    {
        None = 0,
        ClassName = 1 << 0,         // 保留类名
        StructName = 1 << 1,        // 保留结构体名
        InterfaceName = 1 << 2,     // 保留接口名
        EnumName = 1 << 3,          // 保留枚举名
        DelegateName = 1 << 4,      // 保留委托名
        Namespace = 1 << 5,         // 保留命名空间
        MethodName = 1 << 6,        // 保留方法名（高级选项）
        PropertyName = 1 << 7,      // 保留属性名（高级选项）
        FieldName = 1 << 8,         // 保留字段名（高级选项）
        
        AllTypes = ClassName | StructName | InterfaceName | EnumName | DelegateName,
        All = AllTypes | Namespace | MethodName | PropertyName | FieldName
    }

    /// <summary>
    /// 类名保留处理器
    /// </summary>
    public static class ClassNamePreserver
    {
        // 类型声明的正则表达式
        private static readonly Regex TypeDeclarationRegex = new Regex(
            @"(?<modifiers>(?:(?:public|private|protected|internal|abstract|sealed|static|partial|readonly|new)\s+)*)" +
            @"(?<keyword>class|struct|interface|enum|record)\s+" +
            @"(?<name>\w+)" +
            @"(?<generic><[^>]+>)?" +
            @"(?:\s*:\s*(?<base>[^{]+))?",
            RegexOptions.Compiled | RegexOptions.Multiline);

        // 委托声明的正则表达式
        private static readonly Regex DelegateRegex = new Regex(
            @"(?<modifiers>(?:(?:public|private|protected|internal)\s+)*)" +
            @"delegate\s+[\w<>\[\],\s]+\s+(?<name>\w+)\s*" +
            @"(?<generic><[^>]+>)?\s*\(",
            RegexOptions.Compiled | RegexOptions.Multiline);

        // 命名空间的正则表达式
        private static readonly Regex NamespaceRegex = new Regex(
            @"namespace\s+(?<name>[\w.]+)",
            RegexOptions.Compiled | RegexOptions.Multiline);

        // 方法声明的正则表达式
        private static readonly Regex MethodRegex = new Regex(
            @"(?<modifiers>(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|new|partial)\s+)*)" +
            @"(?<return>[\w<>\[\],\s\?]+)\s+" +
            @"(?<name>\w+)\s*" +
            @"(?<generic><[^>]+>)?\s*\(",
            RegexOptions.Compiled | RegexOptions.Multiline);

        /// <summary>
        /// 提取所有类型声明
        /// </summary>
        public static List<TypeDeclaration> ExtractTypeDeclarations(string content)
        {
            var declarations = new List<TypeDeclaration>();
            var lines = content.Split('\n');
            
            // 提取类/结构体/接口/枚举
            var matches = TypeDeclarationRegex.Matches(content);
            foreach (Match match in matches)
            {
                var declaration = new TypeDeclaration
                {
                    FullMatch = match.Value,
                    TypeKeyword = match.Groups["keyword"].Value,
                    TypeName = match.Groups["name"].Value,
                    Modifiers = match.Groups["modifiers"].Value.Trim(),
                    GenericParams = match.Groups["generic"].Value,
                    BaseTypes = match.Groups["base"].Value.Trim(),
                    StartIndex = match.Index,
                    Length = match.Length
                };
                
                declaration.LineNumber = GetLineNumber(content, match.Index);
                declarations.Add(declaration);
            }
            
            // 提取委托
            matches = DelegateRegex.Matches(content);
            foreach (Match match in matches)
            {
                var declaration = new TypeDeclaration
                {
                    FullMatch = match.Value,
                    TypeKeyword = "delegate",
                    TypeName = match.Groups["name"].Value,
                    Modifiers = match.Groups["modifiers"].Value.Trim(),
                    GenericParams = match.Groups["generic"].Value,
                    StartIndex = match.Index,
                    Length = match.Length
                };
                
                declaration.LineNumber = GetLineNumber(content, match.Index);
                declarations.Add(declaration);
            }
            
            return declarations;
        }

        /// <summary>
        /// 提取命名空间
        /// </summary>
        public static List<TypeDeclaration> ExtractNamespaces(string content)
        {
            var namespaces = new List<TypeDeclaration>();
            var matches = NamespaceRegex.Matches(content);
            
            foreach (Match match in matches)
            {
                namespaces.Add(new TypeDeclaration
                {
                    FullMatch = match.Value,
                    TypeKeyword = "namespace",
                    TypeName = match.Groups["name"].Value,
                    StartIndex = match.Index,
                    Length = match.Length,
                    LineNumber = GetLineNumber(content, match.Index)
                });
            }
            
            return namespaces;
        }

        /// <summary>
        /// 应用类名保留 - 将Local中的类名替换为Base中的类名
        /// </summary>
        public static string ApplyNamePreservation(
            string baseContent, 
            string localContent, 
            PreserveOptions options,
            out List<NameReplacement> replacements)
        {
            replacements = new List<NameReplacement>();
            string result = localContent;
            
            // 提取Base和Local的类型声明
            var baseTypes = ExtractTypeDeclarations(baseContent);
            var localTypes = ExtractTypeDeclarations(localContent);
            
            // 如果需要保留命名空间
            if (options.HasFlag(PreserveOptions.Namespace))
            {
                var baseNamespaces = ExtractNamespaces(baseContent);
                var localNamespaces = ExtractNamespaces(localContent);
                
                result = ReplaceNamespaces(result, baseNamespaces, localNamespaces, replacements);
            }
            
            // 匹配并替换类型名
            result = ReplaceTypeNames(result, baseTypes, localTypes, options, replacements);
            
            return result;
        }

        /// <summary>
        /// 替换类型名称
        /// </summary>
        private static string ReplaceTypeNames(
            string content,
            List<TypeDeclaration> baseTypes,
            List<TypeDeclaration> localTypes,
            PreserveOptions options,
            List<NameReplacement> replacements)
        {
            // 按类型匹配
            var matchedPairs = MatchTypesByStructure(baseTypes, localTypes);
            
            foreach (var (baseType, localType) in matchedPairs)
            {
                // 检查是否需要处理此类型
                if (!ShouldPreserve(baseType.TypeKeyword, options))
                    continue;
                
                // 如果名称不同，进行替换
                if (baseType.TypeName != localType.TypeName)
                {
                    var replacement = new NameReplacement
                    {
                        OriginalName = localType.TypeName,
                        NewName = baseType.TypeName,
                        TypeKeyword = baseType.TypeKeyword,
                        LineNumber = localType.LineNumber
                    };
                    
                    // 替换类型声明
                    content = ReplaceTypeName(content, localType.TypeName, baseType.TypeName);
                    
                    replacements.Add(replacement);
                }
            }
            
            return content;
        }

        /// <summary>
        /// 通过结构匹配类型（处理重命名的情况）
        /// </summary>
        private static List<(TypeDeclaration baseType, TypeDeclaration localType)> MatchTypesByStructure(
            List<TypeDeclaration> baseTypes,
            List<TypeDeclaration> localTypes)
        {
            var matched = new List<(TypeDeclaration, TypeDeclaration)>();
            var usedLocal = new HashSet<int>();
            
            // 首先按名称精确匹配
            foreach (var baseType in baseTypes)
            {
                for (int i = 0; i < localTypes.Count; i++)
                {
                    if (usedLocal.Contains(i)) continue;
                    
                    var localType = localTypes[i];
                    if (baseType.TypeName == localType.TypeName && 
                        baseType.TypeKeyword == localType.TypeKeyword)
                    {
                        matched.Add((baseType, localType));
                        usedLocal.Add(i);
                        break;
                    }
                }
            }
            
            // 然后按位置和类型关键字匹配（处理重命名）
            var unmatchedBase = baseTypes.Where(b => !matched.Any(m => m.Item1 == b)).ToList();
            var unmatchedLocal = localTypes.Where((l, i) => !usedLocal.Contains(i)).ToList();
            
            foreach (var baseType in unmatchedBase)
            {
                // 找同类型关键字且位置相近的
                var candidate = unmatchedLocal
                    .Where(l => l.TypeKeyword == baseType.TypeKeyword)
                    .OrderBy(l => Math.Abs(l.LineNumber - baseType.LineNumber))
                    .FirstOrDefault();
                
                if (candidate != null)
                {
                    matched.Add((baseType, candidate));
                    unmatchedLocal.Remove(candidate);
                }
            }
            
            return matched;
        }

        /// <summary>
        /// 替换类型名称（包括所有引用）
        /// </summary>
        private static string ReplaceTypeName(string content, string oldName, string newName)
        {
            // 使用单词边界替换，避免替换部分匹配
            var pattern = $@"\b{Regex.Escape(oldName)}\b";
            return Regex.Replace(content, pattern, newName);
        }

        /// <summary>
        /// 替换命名空间
        /// </summary>
        private static string ReplaceNamespaces(
            string content,
            List<TypeDeclaration> baseNamespaces,
            List<TypeDeclaration> localNamespaces,
            List<NameReplacement> replacements)
        {
            if (baseNamespaces.Count == 0 || localNamespaces.Count == 0)
                return content;
            
            // 简单策略：按顺序匹配
            for (int i = 0; i < Math.Min(baseNamespaces.Count, localNamespaces.Count); i++)
            {
                var baseNs = baseNamespaces[i];
                var localNs = localNamespaces[i];
                
                if (baseNs.TypeName != localNs.TypeName)
                {
                    content = content.Replace(
                        $"namespace {localNs.TypeName}",
                        $"namespace {baseNs.TypeName}");
                    
                    replacements.Add(new NameReplacement
                    {
                        OriginalName = localNs.TypeName,
                        NewName = baseNs.TypeName,
                        TypeKeyword = "namespace",
                        LineNumber = localNs.LineNumber
                    });
                }
            }
            
            return content;
        }

        /// <summary>
        /// 检查是否应该保留此类型的名称
        /// </summary>
        // private static bool ShouldPreserve(string typeKeyword, PreserveOptions options)
        // {
        //     return typeKeyword switch
        //     {
        //         "class" or "record" => options.HasFlag(PreserveOptions.ClassName),
        //         "struct" => options.HasFlag(PreserveOptions.StructName),
        //         "interface" => options.HasFlag(PreserveOptions.InterfaceName),
        //         "enum" => options.HasFlag(PreserveOptions.EnumName),
        //         "delegate" => options.HasFlag(PreserveOptions.DelegateName),
        //         _ => false
        //     };
        // }
        private static bool ShouldPreserve(string typeKeyword, PreserveOptions options)
        {
            switch (typeKeyword)
            {
                case "class":
                case "record":
                    return options.HasFlag(PreserveOptions.ClassName);
                case "struct":
                    return options.HasFlag(PreserveOptions.StructName);
                case "interface":
                    return options.HasFlag(PreserveOptions.InterfaceName);
                case "delegate":
                    return options.HasFlag(PreserveOptions.DelegateName);
                default:
                    return false;
            }
        }

        /// <summary>
        /// 获取指定位置的行号
        /// </summary>
        private static int GetLineNumber(string content, int index)
        {
            int line = 1;
            for (int i = 0; i < index && i < content.Length; i++)
            {
                if (content[i] == '\n') line++;
            }
            return line;
        }

        /// <summary>
        /// 智能检测Base和Local之间的类名映射关系
        /// </summary>
        public static Dictionary<string, string> DetectNameMappings(string baseContent, string localContent)
        {
            var mappings = new Dictionary<string, string>();
            
            var baseTypes = ExtractTypeDeclarations(baseContent);
            var localTypes = ExtractTypeDeclarations(localContent);
            
            var matched = MatchTypesByStructure(baseTypes, localTypes);
            
            foreach (var (baseType, localType) in matched)
            {
                if (baseType.TypeName != localType.TypeName)
                {
                    mappings[localType.TypeName] = baseType.TypeName;
                }
            }
            
            // 检测命名空间
            var baseNs = ExtractNamespaces(baseContent);
            var localNs = ExtractNamespaces(localContent);
            
            for (int i = 0; i < Math.Min(baseNs.Count, localNs.Count); i++)
            {
                if (baseNs[i].TypeName != localNs[i].TypeName)
                {
                    mappings[localNs[i].TypeName] = baseNs[i].TypeName;
                }
            }
            
            return mappings;
        }
    }

    /// <summary>
    /// 名称替换记录
    /// </summary>
    public class NameReplacement
    {
        public string OriginalName;
        public string NewName;
        public string TypeKeyword;
        public int LineNumber;
        
        public override string ToString()
        {
            return $"[{TypeKeyword}] {OriginalName} -> {NewName} (Line {LineNumber})";
        }
    }
}
