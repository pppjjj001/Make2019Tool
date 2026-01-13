using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEditor;

namespace UnityEditor
{
    public class BY_ShaderPropertyFixer : EditorWindow
    {
        private Shader targetShader;
        private MonoScript shaderGUIScript;
        private Vector2 scrollPosition;
        private string previewContent = "";
        private bool showPreview = false;
        
        // 解析结果
        private Dictionary<string, PropertyFixInfo> propertyFixInfos = new Dictionary<string, PropertyFixInfo>();
        private List<string> detectedKeywords = new List<string>();
        private string originalShaderContent = "";
        
        // 修复选项
        private bool fixDisplayNames = true;
        private bool fixToggleAttributes = true;
        private bool fixKeywordEnumAttributes = true;
        private bool addTooltipsAsComments = false;
        private bool backupOriginal = true;
        
        private class PropertyFixInfo
        {
            public string propertyName;
            public string currentDisplayName;
            public string suggestedDisplayName;
            public string currentAttribute;
            public string suggestedAttribute;
            public string associatedKeyword;
            public string[] keywordEnumKeywords;
            public string[] enumValues;
            public bool isToggle;
            public bool isKeywordEnum;
            public bool needsAttributeFix;
            public bool needsDisplayNameFix;
            public string tooltip;
            public int lineNumber;
        }
        
        [MenuItem("Tools/TempByAI/Shader Property Fixer", false, 101)]
        public static void ShowWindow()
        {
            var window = GetWindow<BY_ShaderPropertyFixer>("Shader Property Fixer");
            window.minSize = new Vector2(600, 700);
        }
        
        private void OnGUI()
        {
            EditorGUILayout.Space(10);
            EditorGUILayout.LabelField("BY Shader 属性修复工具", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "此工具可以：\n" +
                "1. 根据ShaderGUI代码中的Styles还原Shader属性的显示名称\n" +
                "2. 自动补全Toggle属性缺少的[Toggle(KEYWORD)]声明\n" +
                "3. 自动补全KeywordEnum属性缺少的声明", 
                MessageType.Info);
            
            EditorGUILayout.Space(5);
            DrawLine();
            
            // 输入区域
            EditorGUILayout.LabelField("输入设置", EditorStyles.boldLabel);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("目标Shader:", GUILayout.Width(100));
            EditorGUI.BeginChangeCheck();
            targetShader = (Shader)EditorGUILayout.ObjectField(targetShader, typeof(Shader), false);
            if (EditorGUI.EndChangeCheck())
            {
                ClearAnalysis();
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("ShaderGUI脚本:", GUILayout.Width(100));
            EditorGUI.BeginChangeCheck();
            shaderGUIScript = (MonoScript)EditorGUILayout.ObjectField(shaderGUIScript, typeof(MonoScript), false);
            if (EditorGUI.EndChangeCheck())
            {
                ClearAnalysis();
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(5);
            DrawLine();
            
            // 修复选项
            EditorGUILayout.LabelField("修复选项", EditorStyles.boldLabel);
            fixDisplayNames = EditorGUILayout.Toggle("修复显示名称", fixDisplayNames);
            fixToggleAttributes = EditorGUILayout.Toggle("补全Toggle属性", fixToggleAttributes);
            fixKeywordEnumAttributes = EditorGUILayout.Toggle("补全KeywordEnum属性", fixKeywordEnumAttributes);
            addTooltipsAsComments = EditorGUILayout.Toggle("添加Tooltip注释", addTooltipsAsComments);
            backupOriginal = EditorGUILayout.Toggle("备份原文件", backupOriginal);
            
            EditorGUILayout.Space(5);
            DrawLine();
            
            // 操作按钮
            EditorGUILayout.BeginHorizontal();
            
            GUI.enabled = targetShader != null;
            
            if (GUILayout.Button("分析Shader", GUILayout.Height(30)))
            {
                AnalyzeShader();
                showPreview = false;
            }
            
            if (GUILayout.Button("预览修改", GUILayout.Height(30)))
            {
                if (propertyFixInfos.Count == 0)
                {
                    AnalyzeShader();
                }
                GenerateFixedShader();
                showPreview = true;
            }
            
            GUI.enabled = targetShader != null && !string.IsNullOrEmpty(previewContent);
            
            if (GUILayout.Button("应用修改", GUILayout.Height(30)))
            {
                if (string.IsNullOrEmpty(previewContent))
                {
                    GenerateFixedShader();
                }
                ApplyFixes();
            }
            
            GUI.enabled = true;
            
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(10);
            
            // 显示分析结果或预览
            if (showPreview && !string.IsNullOrEmpty(previewContent))
            {
                EditorGUILayout.LabelField("修改预览", EditorStyles.boldLabel);
                scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
                
                var codeStyle = new GUIStyle(EditorStyles.textArea);
                codeStyle.wordWrap = false;
                
                EditorGUILayout.TextArea(previewContent, codeStyle, GUILayout.ExpandHeight(true));
                EditorGUILayout.EndScrollView();
            }
            else if (propertyFixInfos.Count > 0)
            {
                DrawAnalysisResults();
            }
        }
        
        private void DrawLine()
        {
            EditorGUILayout.Space(5);
            var rect = EditorGUILayout.GetControlRect(false, 1);
            EditorGUI.DrawRect(rect, new Color(0.5f, 0.5f, 0.5f, 1));
            EditorGUILayout.Space(5);
        }
        
        private void ClearAnalysis()
        {
            propertyFixInfos.Clear();
            detectedKeywords.Clear();
            previewContent = "";
            showPreview = false;
        }
        
        private void DrawAnalysisResults()
        {
            EditorGUILayout.LabelField($"分析结果 ({propertyFixInfos.Count} 个属性)", EditorStyles.boldLabel);
            
            // 统计
            int needsDisplayNameFix = propertyFixInfos.Values.Count(p => p.needsDisplayNameFix);
            int needsAttributeFix = propertyFixInfos.Values.Count(p => p.needsAttributeFix);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField($"需要修复显示名称: {needsDisplayNameFix}", EditorStyles.miniLabel);
            EditorGUILayout.LabelField($"需要补全属性: {needsAttributeFix}", EditorStyles.miniLabel);
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(5);
            
            scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
            
            // 表头
            EditorGUILayout.BeginHorizontal("box");
            EditorGUILayout.LabelField("属性名", EditorStyles.boldLabel, GUILayout.Width(150));
            EditorGUILayout.LabelField("当前", EditorStyles.boldLabel, GUILayout.Width(150));
            EditorGUILayout.LabelField("建议", EditorStyles.boldLabel, GUILayout.Width(150));
            EditorGUILayout.LabelField("状态", EditorStyles.boldLabel, GUILayout.Width(100));
            EditorGUILayout.EndHorizontal();
            
            foreach (var kvp in propertyFixInfos)
            {
                var info = kvp.Value;
                
                bool hasIssue = info.needsDisplayNameFix || info.needsAttributeFix;
                
                var bgColor = GUI.backgroundColor;
                if (hasIssue)
                {
                    GUI.backgroundColor = new Color(1f, 0.9f, 0.7f);
                }
                
                EditorGUILayout.BeginHorizontal("box");
                
                EditorGUILayout.LabelField(info.propertyName, GUILayout.Width(150));
                
                // 当前状态
                string currentInfo = info.currentDisplayName ?? "-";
                if (!string.IsNullOrEmpty(info.currentAttribute))
                {
                    currentInfo += $"\n[{info.currentAttribute}]";
                }
                EditorGUILayout.LabelField(currentInfo, EditorStyles.wordWrappedMiniLabel, GUILayout.Width(150));
                
                // 建议修改
                string suggestedInfo = "";
                if (info.needsDisplayNameFix && !string.IsNullOrEmpty(info.suggestedDisplayName))
                {
                    suggestedInfo = info.suggestedDisplayName;
                }
                if (info.needsAttributeFix && !string.IsNullOrEmpty(info.suggestedAttribute))
                {
                    if (!string.IsNullOrEmpty(suggestedInfo)) suggestedInfo += "\n";
                    suggestedInfo += $"[{info.suggestedAttribute}]";
                }
                if (string.IsNullOrEmpty(suggestedInfo)) suggestedInfo = "-";
                EditorGUILayout.LabelField(suggestedInfo, EditorStyles.wordWrappedMiniLabel, GUILayout.Width(150));
                
                // 状态
                string status = "✓ OK";
                if (info.needsDisplayNameFix && info.needsAttributeFix)
                    status = "⚠ 需修复";
                else if (info.needsDisplayNameFix)
                    status = "⚠ 名称";
                else if (info.needsAttributeFix)
                    status = "⚠ 属性";
                
                EditorGUILayout.LabelField(status, GUILayout.Width(100));
                
                EditorGUILayout.EndHorizontal();
                
                GUI.backgroundColor = bgColor;
            }
            
            EditorGUILayout.EndScrollView();
        }
        
        private void AnalyzeShader()
        {
            propertyFixInfos.Clear();
            detectedKeywords.Clear();
            
            if (targetShader == null)
            {
                EditorUtility.DisplayDialog("错误", "请选择目标Shader", "确定");
                return;
            }
            
            // 读取Shader源码
            string shaderPath = AssetDatabase.GetAssetPath(targetShader);
            if (string.IsNullOrEmpty(shaderPath) || !File.Exists(shaderPath))
            {
                EditorUtility.DisplayDialog("错误", "无法读取Shader文件", "确定");
                return;
            }
            
            originalShaderContent = File.ReadAllText(shaderPath);
            
            // 解析Shader中的Properties
            ParseShaderProperties(originalShaderContent);
            
            // 解析Shader中的关键字
            ParseShaderKeywords(originalShaderContent);
            
            // 如果有ShaderGUI脚本，解析其中的信息
            if (shaderGUIScript != null)
            {
                string guiScriptPath = AssetDatabase.GetAssetPath(shaderGUIScript);
                if (!string.IsNullOrEmpty(guiScriptPath) && File.Exists(guiScriptPath))
                {
                    string guiContent = File.ReadAllText(guiScriptPath);
                    ParseShaderGUIScript(guiContent);
                }
            }
            
            // 分析并确定需要修复的内容
            AnalyzeFixRequirements();
            
            Debug.Log($"分析完成: {propertyFixInfos.Count} 个属性, {detectedKeywords.Count} 个关键字");
        }
        
        private void ParseShaderProperties(string shaderContent)
        {
            var propertiesMatch = Regex.Match(shaderContent, @"Properties\s*\{([\s\S]*?)\n\s*\}", RegexOptions.Multiline);
            if (!propertiesMatch.Success)
            {
                Debug.LogWarning("未找到Properties块");
                return;
            }
            
            string propertiesBlock = propertiesMatch.Groups[1].Value;
            string[] lines = propertiesBlock.Split(new[] { '\n' }, StringSplitOptions.None);
            
            int lineNumber = 0;
            foreach (string line in lines)
            {
                lineNumber++;
                string trimmedLine = line.Trim();
                
                if (string.IsNullOrEmpty(trimmedLine) || trimmedLine.StartsWith("//"))
                    continue;
                
                // 匹配属性定义: _PropertyName ("Display Name", Type) = Value
                var propMatch = Regex.Match(trimmedLine, 
                    @"(_[A-Za-z][A-Za-z0-9_]*)\s*\(\s*""([^""]*)""\s*,\s*([^)]+)\)");
                
                if (!propMatch.Success)
                    continue;
                
                string propName = propMatch.Groups[1].Value;
                string displayName = propMatch.Groups[2].Value;
                string propType = propMatch.Groups[3].Value.Trim();
                
                var info = new PropertyFixInfo
                {
                    propertyName = propName,
                    currentDisplayName = displayName,
                    lineNumber = lineNumber
                };
                
                // 检查现有的Attribute
                ParseExistingAttributes(trimmedLine, info);
                
                propertyFixInfos[propName] = info;
            }
        }
        
        private void ParseExistingAttributes(string line, PropertyFixInfo info)
        {
            // [Toggle(KEYWORD)]
            var toggleWithKeyword = Regex.Match(line, @"\[Toggle\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)\s*\]", RegexOptions.IgnoreCase);
            if (toggleWithKeyword.Success)
            {
                info.currentAttribute = $"Toggle({toggleWithKeyword.Groups[1].Value})";
                info.associatedKeyword = toggleWithKeyword.Groups[1].Value;
                info.isToggle = true;
                return;
            }
            
            // [Toggle]
            if (Regex.IsMatch(line, @"\[Toggle\s*\]", RegexOptions.IgnoreCase))
            {
                info.currentAttribute = "Toggle";
                info.isToggle = true;
                return;
            }
            
            // [ToggleOff]
            if (Regex.IsMatch(line, @"\[ToggleOff\s*\]", RegexOptions.IgnoreCase))
            {
                info.currentAttribute = "ToggleOff";
                info.isToggle = true;
                return;
            }
            
            // [KeywordEnum(A, B, C)]
            var keywordEnum = Regex.Match(line, @"\[KeywordEnum\s*\(\s*([^)]+)\s*\)\s*\]", RegexOptions.IgnoreCase);
            if (keywordEnum.Success)
            {
                string enumValues = keywordEnum.Groups[1].Value;
                info.currentAttribute = $"KeywordEnum({enumValues})";
                info.enumValues = enumValues.Split(',').Select(v => v.Trim()).ToArray();
                info.isKeywordEnum = true;
                
                // 生成对应的关键字
                string propUpper = info.propertyName.ToUpper();
                info.keywordEnumKeywords = info.enumValues.Select(v => $"{propUpper}_{v.ToUpper()}").ToArray();
                return;
            }
            
            // [Enum(...)]
            var enumAttr = Regex.Match(line, @"\[Enum\s*\(\s*([^)]+)\s*\)\s*\]", RegexOptions.IgnoreCase);
            if (enumAttr.Success)
            {
                info.currentAttribute = $"Enum({enumAttr.Groups[1].Value})";
                return;
            }
        }
        
        private void ParseShaderKeywords(string shaderContent)
        {
            var pragmaPatterns = new string[]
            {
                @"#pragma\s+shader_feature(?:_local)?\s+(.+)",
                @"#pragma\s+multi_compile(?:_local)?\s+(.+)"
            };
            
            foreach (var pattern in pragmaPatterns)
            {
                var regex = new Regex(pattern, RegexOptions.Multiline);
                var matches = regex.Matches(shaderContent);
                
                foreach (Match match in matches)
                {
                    string keywordsLine = match.Groups[1].Value.Trim();
                    
                    int commentIndex = keywordsLine.IndexOf("//");
                    if (commentIndex >= 0)
                    {
                        keywordsLine = keywordsLine.Substring(0, commentIndex);
                    }
                    
                    var keywords = keywordsLine.Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    
                    foreach (var keyword in keywords)
                    {
                        string kw = keyword.Trim();
                        if (!string.IsNullOrEmpty(kw) && kw != "_" && !detectedKeywords.Contains(kw))
                        {
                            detectedKeywords.Add(kw);
                        }
                    }
                }
            }
        }
        
        private void ParseShaderGUIScript(string guiContent)
        {
            // 解析Styles类中的GUIContent定义
            // 格式: public static GUIContent xxxText = new GUIContent("Display Name", "Tooltip");
            var stylePattern = new Regex(
                @"public\s+static\s+GUIContent\s+(\w+)Text\s*=\s*new\s+GUIContent\s*\(\s*""([^""]*)""\s*(?:,\s*""([^""]*)"")?\s*\)",
                RegexOptions.Multiline);
            
            var matches = stylePattern.Matches(guiContent);
            
            foreach (Match match in matches)
            {
                string varName = match.Groups[1].Value;
                string displayName = match.Groups[2].Value;
                string tooltip = match.Groups[3].Success ? match.Groups[3].Value : "";
                
                // 从变量名推断属性名
                string propName = "_" + char.ToUpper(varName[0]) + varName.Substring(1);
                
                // 尝试在已有属性中查找
                if (propertyFixInfos.ContainsKey(propName))
                {
                    var info = propertyFixInfos[propName];
                    info.suggestedDisplayName = displayName;
                    info.tooltip = tooltip;
                }
                else
                {
                    // 尝试其他命名变体
                    string altPropName = "_" + varName;
                    if (propertyFixInfos.ContainsKey(altPropName))
                    {
                        var info = propertyFixInfos[altPropName];
                        info.suggestedDisplayName = displayName;
                        info.tooltip = tooltip;
                    }
                }
            }
            
            // 解析SetMaterialKeywords方法中的关键字映射
            // 格式: CoreUtils.SetKeyword(material, "KEYWORD_NAME", material.GetFloat("_PropertyName") == 1.0f);
            var keywordPattern = new Regex(
                @"CoreUtils\.SetKeyword\s*\(\s*material\s*,\s*""([^""]+)""\s*,\s*material\.GetFloat\s*\(\s*""([^""]+)""\s*\)",
                RegexOptions.Multiline);
            
            var keywordMatches = keywordPattern.Matches(guiContent);
            
            foreach (Match match in keywordMatches)
            {
                string keyword = match.Groups[1].Value;
                string propName = match.Groups[2].Value;
                
                if (propertyFixInfos.ContainsKey(propName))
                {
                    var info = propertyFixInfos[propName];
                    if (string.IsNullOrEmpty(info.associatedKeyword))
                    {
                        info.associatedKeyword = keyword;
                    }
                }
            }
            
            // 解析KeywordEnum的关键字列表
            // 格式: CoreUtils.SetKeyword(material, "_PROPNAME_VALUE", propNameValue == 0);
            var keywordEnumPattern = new Regex(
                @"int\s+(\w+)Value\s*=.*?GetFloat\s*\(\s*""([^""]+)""\s*\)",
                RegexOptions.Multiline);
            
            var enumMatches = keywordEnumPattern.Matches(guiContent);
            
            foreach (Match match in enumMatches)
            {
                string varName = match.Groups[1].Value;
                string propName = match.Groups[2].Value;
                
                if (propertyFixInfos.ContainsKey(propName))
                {
                    var info = propertyFixInfos[propName];
                    
                    // 收集该属性的所有关键字
                    var enumKeywordPattern = new Regex(
                        $@"CoreUtils\.SetKeyword\s*\(\s*material\s*,\s*""([^""]+)""\s*,\s*{varName}Value\s*==\s*(\d+)\s*\)",
                        RegexOptions.Multiline);
                    
                    var enumKeywordMatches = enumKeywordPattern.Matches(guiContent);
                    var keywords = new List<string>();
                    
                    foreach (Match km in enumKeywordMatches)
                    {
                        keywords.Add(km.Groups[1].Value);
                    }
                    
                    if (keywords.Count > 0)
                    {
                        info.keywordEnumKeywords = keywords.ToArray();
                        info.isKeywordEnum = true;
                    }
                }
            }
        }
        
        private void AnalyzeFixRequirements()
        {
            foreach (var kvp in propertyFixInfos)
            {
                var info = kvp.Value;
                
                // 检查显示名称是否需要修复
                if (!string.IsNullOrEmpty(info.suggestedDisplayName) && 
                    info.suggestedDisplayName != info.currentDisplayName)
                {
                    info.needsDisplayNameFix = fixDisplayNames;
                }
                
                // 检查Toggle属性是否需要补全
                if (fixToggleAttributes && !string.IsNullOrEmpty(info.associatedKeyword))
                {
                    // 如果有关联的关键字，但当前没有正确的Toggle属性
                    if (info.currentAttribute == "Toggle" || string.IsNullOrEmpty(info.currentAttribute))
                    {
                        // 检查关键字是否存在于Shader中
                        if (detectedKeywords.Contains(info.associatedKeyword))
                        {
                            if (info.associatedKeyword.EndsWith("_OFF"))
                            {
                                info.suggestedAttribute = "ToggleOff";
                            }
                            else
                            {
                                info.suggestedAttribute = $"Toggle({info.associatedKeyword})";
                            }
                            info.needsAttributeFix = true;
                        }
                    }
                }
                
                // 检查KeywordEnum属性
                if (fixKeywordEnumAttributes && info.isKeywordEnum && 
                    info.keywordEnumKeywords != null && info.keywordEnumKeywords.Length > 0)
                {
                    if (string.IsNullOrEmpty(info.currentAttribute) || 
                        !info.currentAttribute.StartsWith("KeywordEnum"))
                    {
                        // 从关键字推断枚举值
                        var enumValues = InferEnumValuesFromKeywords(info.propertyName, info.keywordEnumKeywords);
                        if (enumValues.Length > 0)
                        {
                            info.suggestedAttribute = $"KeywordEnum({string.Join(", ", enumValues)})";
                            info.needsAttributeFix = true;
                        }
                    }
                }
            }
        }
        
        private string[] InferEnumValuesFromKeywords(string propertyName, string[] keywords)
        {
            string prefix = propertyName.ToUpper() + "_";
            var values = new List<string>();
            
            foreach (var keyword in keywords)
            {
                if (keyword.StartsWith(prefix))
                {
                    string value = keyword.Substring(prefix.Length);
                    // 转换为首字母大写格式
                    value = char.ToUpper(value[0]) + value.Substring(1).ToLower();
                    values.Add(value);
                }
            }
            
            return values.ToArray();
        }
        
        private void GenerateFixedShader()
        {
            if (string.IsNullOrEmpty(originalShaderContent))
            {
                string shaderPath = AssetDatabase.GetAssetPath(targetShader);
                originalShaderContent = File.ReadAllText(shaderPath);
            }
            
            string fixedContent = originalShaderContent;
            
            // 找到Properties块
            var propertiesMatch = Regex.Match(fixedContent, @"(Properties\s*\{)([\s\S]*?)(\n\s*\})", RegexOptions.Multiline);
            if (!propertiesMatch.Success)
            {
                previewContent = "// 错误：未找到Properties块";
                return;
            }
            
            string propertiesBlock = propertiesMatch.Groups[2].Value;
            string[] lines = propertiesBlock.Split(new[] { '\n' }, StringSplitOptions.None);
            
            var newLines = new List<string>();
            
            foreach (string line in lines)
            {
                string processedLine = ProcessPropertyLine(line);
                newLines.Add(processedLine);
            }
            
            string newPropertiesBlock = string.Join("\n", newLines);
            
            fixedContent = fixedContent.Substring(0, propertiesMatch.Groups[2].Index) +
                          newPropertiesBlock +
                          fixedContent.Substring(propertiesMatch.Groups[2].Index + propertiesMatch.Groups[2].Length);
            
            previewContent = fixedContent;
        }
        
        private string ProcessPropertyLine(string line)
        {
            string trimmedLine = line.Trim();
            
            if (string.IsNullOrEmpty(trimmedLine) || trimmedLine.StartsWith("//"))
                return line;
            
            // 匹配属性名
            var propMatch = Regex.Match(trimmedLine, @"(_[A-Za-z][A-Za-z0-9_]*)\s*\(");
            if (!propMatch.Success)
                return line;
            
            string propName = propMatch.Groups[1].Value;
            
            if (!propertyFixInfos.ContainsKey(propName))
                return line;
            
            var info = propertyFixInfos[propName];
            string newLine = line;
            
            // 修复显示名称
            if (info.needsDisplayNameFix && !string.IsNullOrEmpty(info.suggestedDisplayName))
            {
                var displayNameMatch = Regex.Match(newLine, @"(""\s*)([^""]*?)(\s*""\s*,)");
                if (displayNameMatch.Success)
                {
                    newLine = newLine.Substring(0, displayNameMatch.Groups[2].Index) +
                             info.suggestedDisplayName +
                             newLine.Substring(displayNameMatch.Groups[2].Index + displayNameMatch.Groups[2].Length);
                }
            }
            
            // 修复/添加属性
            if (info.needsAttributeFix && !string.IsNullOrEmpty(info.suggestedAttribute))
            {
                // 移除现有的Toggle/KeywordEnum属性
                newLine = Regex.Replace(newLine, @"\[Toggle\s*(?:\([^)]*\))?\s*\]\s*", "");
                newLine = Regex.Replace(newLine, @"\[ToggleOff\s*\]\s*", "");
                newLine = Regex.Replace(newLine, @"\[KeywordEnum\s*\([^)]*\)\s*\]\s*", "");
                
                // 在属性名前添加新的属性
                int propIndex = newLine.IndexOf(propName);
                if (propIndex > 0)
                {
                    // 获取缩进
                    string indent = "";
                    for (int i = 0; i < propIndex; i++)
                    {
                        if (newLine[i] == ' ' || newLine[i] == '\t')
                            indent += newLine[i];
                        else
                            break;
                    }
                    
                    newLine = indent + $"[{info.suggestedAttribute}] " + newLine.TrimStart();
                }
            }
            
            // 添加tooltip注释
            if (addTooltipsAsComments && !string.IsNullOrEmpty(info.tooltip))
            {
                if (!newLine.TrimEnd().EndsWith("//"))
                {
                    newLine = newLine.TrimEnd() + $" // {info.tooltip}";
                }
            }
            
            return newLine;
        }
        
        private void ApplyFixes()
        {
            if (string.IsNullOrEmpty(previewContent))
            {
                EditorUtility.DisplayDialog("错误", "没有可应用的修改", "确定");
                return;
            }
            
            string shaderPath = AssetDatabase.GetAssetPath(targetShader);
            
            // 备份原文件
            if (backupOriginal)
            {
                string backupPath = shaderPath + ".backup";
                int counter = 1;
                while (File.Exists(backupPath))
                {
                    backupPath = shaderPath + $".backup{counter}";
                    counter++;
                }
                
                File.Copy(shaderPath, backupPath);
                Debug.Log($"已备份原文件到: {backupPath}");
            }
            
            // 写入修改后的内容
            File.WriteAllText(shaderPath, previewContent, Encoding.UTF8);
            
            AssetDatabase.Refresh();
            
            EditorUtility.DisplayDialog("成功", 
                $"已应用修改到:\n{shaderPath}\n\n" +
                $"修复了 {propertyFixInfos.Values.Count(p => p.needsDisplayNameFix)} 个显示名称\n" +
                $"补全了 {propertyFixInfos.Values.Count(p => p.needsAttributeFix)} 个属性声明", 
                "确定");
            
            // 重新选中Shader
            Selection.activeObject = targetShader;
            EditorGUIUtility.PingObject(targetShader);
        }
    }
}
