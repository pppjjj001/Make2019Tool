// using System;
// using System.Collections.Generic;
// using System.IO;
// using System.Linq;
// using System.Text;
// using System.Text.RegularExpressions;
// using UnityEngine;
// using UnityEditor;
//
// namespace UnityEditor
// {
//     public class BY_ShaderGUIGenerator : EditorWindow
//     {
//         private Shader selectedShader;
//         private string outputClassName = "CustomShaderGUI";
//         private string outputNamespace = "UnityEditor";
//         private Vector2 scrollPosition;
//         private string generatedCode = "";
//         private bool showPreview = false;
//         private string outputPath = "Assets/Editor/";
//         
//         // 属性分组配置
//         private bool groupByPrefix = true;
//         private bool generateFoldouts = true;
//         private bool generateKeywords = true;
//         
//         // 属性信息结构
//         private class ShaderPropertyInfo
//         {
//             public string name;
//             public string displayName;
//             public ShaderUtil.ShaderPropertyType type;
//             public string description;
//             public bool isToggle;
//             public string keywordName;
//             public float rangeMin;
//             public float rangeMax;
//             public string[] enumNames;
//         }
//
//         [MenuItem("Tools/TempByAI/Shader GUI Generator", false, 100)]
//         public static void ShowWindow()
//         {
//             var window = GetWindow<BY_ShaderGUIGenerator>("Shader GUI Generator");
//             window.minSize = new Vector2(500, 600);
//         }
//
//         private void OnGUI()
//         {
//             EditorGUILayout.Space(10);
//             EditorGUILayout.LabelField("BY Shader GUI 自动生成工具", EditorStyles.boldLabel);
//             EditorGUILayout.Space(5);
//             
//             DrawLine();
//             
//             // Shader选择
//             EditorGUILayout.BeginHorizontal();
//             EditorGUILayout.LabelField("选择Shader:", GUILayout.Width(80));
//             selectedShader = (Shader)EditorGUILayout.ObjectField(selectedShader, typeof(Shader), false);
//             EditorGUILayout.EndHorizontal();
//             
//             EditorGUILayout.Space(5);
//             
//             // 输出设置
//             EditorGUILayout.LabelField("输出设置", EditorStyles.boldLabel);
//             
//             EditorGUILayout.BeginHorizontal();
//             EditorGUILayout.LabelField("类名:", GUILayout.Width(80));
//             outputClassName = EditorGUILayout.TextField(outputClassName);
//             EditorGUILayout.EndHorizontal();
//             
//             EditorGUILayout.BeginHorizontal();
//             EditorGUILayout.LabelField("命名空间:", GUILayout.Width(80));
//             outputNamespace = EditorGUILayout.TextField(outputNamespace);
//             EditorGUILayout.EndHorizontal();
//             
//             EditorGUILayout.BeginHorizontal();
//             EditorGUILayout.LabelField("输出路径:", GUILayout.Width(80));
//             outputPath = EditorGUILayout.TextField(outputPath);
//             if (GUILayout.Button("浏览", GUILayout.Width(50)))
//             {
//                 string path = EditorUtility.OpenFolderPanel("选择输出目录", outputPath, "");
//                 if (!string.IsNullOrEmpty(path))
//                 {
//                     outputPath = "Assets" + path.Substring(Application.dataPath.Length) + "/";
//                 }
//             }
//             EditorGUILayout.EndHorizontal();
//             
//             EditorGUILayout.Space(5);
//             
//             // 生成选项
//             EditorGUILayout.LabelField("生成选项", EditorStyles.boldLabel);
//             groupByPrefix = EditorGUILayout.Toggle("按前缀分组", groupByPrefix);
//             generateFoldouts = EditorGUILayout.Toggle("生成折叠面板", generateFoldouts);
//             generateKeywords = EditorGUILayout.Toggle("生成Keyword控制", generateKeywords);
//             
//             EditorGUILayout.Space(10);
//             DrawLine();
//             
//             // 操作按钮
//             EditorGUILayout.BeginHorizontal();
//             
//             GUI.enabled = selectedShader != null;
//             
//             if (GUILayout.Button("预览代码", GUILayout.Height(30)))
//             {
//                 generatedCode = GenerateShaderGUICode();
//                 showPreview = true;
//             }
//             
//             if (GUILayout.Button("生成并保存", GUILayout.Height(30)))
//             {
//                 generatedCode = GenerateShaderGUICode();
//                 SaveGeneratedCode();
//             }
//             
//             GUI.enabled = true;
//             
//             if (GUILayout.Button("复制到剪贴板", GUILayout.Height(30)))
//             {
//                 if (!string.IsNullOrEmpty(generatedCode))
//                 {
//                     EditorGUIUtility.systemCopyBuffer = generatedCode;
//                     EditorUtility.DisplayDialog("成功", "代码已复制到剪贴板", "确定");
//                 }
//             }
//             
//             EditorGUILayout.EndHorizontal();
//             
//             EditorGUILayout.Space(10);
//             
//             // 代码预览
//             if (showPreview && !string.IsNullOrEmpty(generatedCode))
//             {
//                 EditorGUILayout.LabelField("代码预览", EditorStyles.boldLabel);
//                 scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
//                 EditorGUILayout.TextArea(generatedCode, GUILayout.ExpandHeight(true));
//                 EditorGUILayout.EndScrollView();
//             }
//             
//             // Shader属性列表
//             if (selectedShader != null && !showPreview)
//             {
//                 EditorGUILayout.LabelField("Shader属性列表", EditorStyles.boldLabel);
//                 scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
//                 DrawShaderProperties();
//                 EditorGUILayout.EndScrollView();
//             }
//         }
//
//         private void DrawLine()
//         {
//             EditorGUILayout.Space(5);
//             var rect = EditorGUILayout.GetControlRect(false, 1);
//             EditorGUI.DrawRect(rect, new Color(0.5f, 0.5f, 0.5f, 1));
//             EditorGUILayout.Space(5);
//         }
//
//         private void DrawShaderProperties()
//         {
//             if (selectedShader == null) return;
//             
//             int propertyCount = ShaderUtil.GetPropertyCount(selectedShader);
//             
//             EditorGUILayout.LabelField($"共 {propertyCount} 个属性", EditorStyles.miniLabel);
//             EditorGUILayout.Space(5);
//             
//             for (int i = 0; i < propertyCount; i++)
//             {
//                 string name = ShaderUtil.GetPropertyName(selectedShader, i);
//                 string desc = ShaderUtil.GetPropertyDescription(selectedShader, i);
//                 var type = ShaderUtil.GetPropertyType(selectedShader, i);
//                 
//                 EditorGUILayout.BeginHorizontal("box");
//                 EditorGUILayout.LabelField(name, GUILayout.Width(200));
//                 EditorGUILayout.LabelField(type.ToString(), GUILayout.Width(80));
//                 EditorGUILayout.LabelField(desc);
//                 EditorGUILayout.EndHorizontal();
//             }
//         }
//
//         private List<ShaderPropertyInfo> GetShaderProperties()
//         {
//             var properties = new List<ShaderPropertyInfo>();
//             
//             if (selectedShader == null) return properties;
//             
//             int propertyCount = ShaderUtil.GetPropertyCount(selectedShader);
//             
//             for (int i = 0; i < propertyCount; i++)
//             {
//                 var prop = new ShaderPropertyInfo
//                 {
//                     name = ShaderUtil.GetPropertyName(selectedShader, i),
//                     displayName = ShaderUtil.GetPropertyDescription(selectedShader, i),
//                     type = ShaderUtil.GetPropertyType(selectedShader, i),
//                 };
//                 
//                 // 检查是否是Toggle属性
//                 prop.isToggle = prop.displayName.Contains("[Toggle]") || 
//                                IsToggleProperty(prop.name);
//                 
//                 // 获取Range范围
//                 if (prop.type == ShaderUtil.ShaderPropertyType.Range)
//                 {
//                     prop.rangeMin = ShaderUtil.GetRangeLimits(selectedShader, i, 1);
//                     prop.rangeMax = ShaderUtil.GetRangeLimits(selectedShader, i, 2);
//                 }
//                 
//                 // 生成描述
//                 prop.description = GeneratePropertyDescription(prop.name, prop.displayName);
//                 
//                 // 生成关键字名称
//                 if (prop.isToggle && generateKeywords)
//                 {
//                     prop.keywordName = GenerateKeywordName(prop.name);
//                 }
//                 
//                 properties.Add(prop);
//             }
//             
//             return properties;
//         }
//
//         private bool IsToggleProperty(string name)
//         {
//             string lower = name.ToLower();
//             return lower.Contains("open") || lower.Contains("enable") || 
//                    lower.Contains("on") || lower.Contains("use") ||
//                    name.StartsWith("_") && name.Length > 1 && char.IsUpper(name[1]) &&
//                    (name.Contains("Open") || name.Contains("Enable") || name.Contains("On"));
//         }
//
//         private string GenerateKeywordName(string propertyName)
//         {
//             // 将属性名转换为关键字名称
//             // 例如: _CubeMapOpen -> _CUBEMAP_ON
//             string keyword = propertyName.TrimStart('_').ToUpper();
//             keyword = Regex.Replace(keyword, "([A-Z])", "_$1").TrimStart('_');
//             keyword = keyword.Replace("OPEN", "ON").Replace("ENABLE", "ON");
//             return "_" + keyword;
//         }
//
//         private string GeneratePropertyDescription(string name, string displayName)
//         {
//             if (!string.IsNullOrEmpty(displayName) && displayName != name)
//             {
//                 return displayName;
//             }
//             
//             // 从属性名生成描述
//             string desc = name.TrimStart('_');
//             desc = Regex.Replace(desc, "(\\B[A-Z])", " $1");
//             return desc;
//         }
//
//         private string GenerateShaderGUICode()
//         {
//             if (selectedShader == null) return "";
//             
//             var properties = GetShaderProperties();
//             var sb = new StringBuilder();
//             
//             // 文件头
//             sb.AppendLine("using System;");
//             sb.AppendLine("using UnityEngine;");
//             sb.AppendLine("using UnityEngine.Rendering;");
//             sb.AppendLine();
//             
//             // 命名空间开始
//             if (!string.IsNullOrEmpty(outputNamespace))
//             {
//                 sb.AppendLine($"namespace {outputNamespace}");
//                 sb.AppendLine("{");
//             }
//             
//             // 类定义
//             sb.AppendLine($"    public class {outputClassName} : ShaderGUI");
//             sb.AppendLine("    {");
//             
//             // 生成Styles类
//             GenerateStylesClass(sb, properties);
//             
//             // 生成CustomProperties结构
//             GeneratePropertiesStruct(sb, properties);
//             
//             // 生成成员变量
//             sb.AppendLine("        private CustomProperties properties;");
//             sb.AppendLine("        private MaterialEditor materialEditor;");
//             
//             if (generateFoldouts)
//             {
//                 GenerateFoldoutVariables(sb, properties);
//             }
//             
//             sb.AppendLine();
//             
//             // 生成OnGUI方法
//             GenerateOnGUIMethod(sb);
//             
//             // 生成FindProperties方法
//             GenerateFindPropertiesMethod(sb);
//             
//             // 生成MaterialChanged方法
//             GenerateMaterialChangedMethod(sb);
//             
//             // 生成SetMaterialKeywords方法
//             if (generateKeywords)
//             {
//                 GenerateSetKeywordsMethod(sb, properties);
//             }
//             
//             // 生成ShaderPropertiesGUI方法
//             GenerateShaderPropertiesGUIMethod(sb, properties);
//             
//             // 类结束
//             sb.AppendLine("    }");
//             
//             // 命名空间结束
//             if (!string.IsNullOrEmpty(outputNamespace))
//             {
//                 sb.AppendLine("}");
//             }
//             
//             return sb.ToString();
//         }
//
//         private void GenerateStylesClass(StringBuilder sb, List<ShaderPropertyInfo> properties)
//         {
//             sb.AppendLine("        private static class Styles");
//             sb.AppendLine("        {");
//             
//             foreach (var prop in properties)
//             {
//                 string varName = GetStyleVariableName(prop.name);
//                 string description = EscapeString(prop.description);
//                 string tooltip = EscapeString(GenerateTooltip(prop));
//                 
//                 if (string.IsNullOrEmpty(tooltip))
//                 {
//                     sb.AppendLine($"            public static GUIContent {varName} = new GUIContent(\"{description}\");");
//                 }
//                 else
//                 {
//                     sb.AppendLine($"            public static GUIContent {varName} = new GUIContent(\"{description}\", \"{tooltip}\");");
//                 }
//             }
//             
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GeneratePropertiesStruct(StringBuilder sb, List<ShaderPropertyInfo> properties)
//         {
//             sb.AppendLine("        private struct CustomProperties");
//             sb.AppendLine("        {");
//             
//             // 声明所有属性
//             foreach (var prop in properties)
//             {
//                 string varName = GetPropertyVariableName(prop.name);
//                 sb.AppendLine($"            public MaterialProperty {varName};");
//             }
//             
//             sb.AppendLine();
//             
//             // 构造函数
//             sb.AppendLine("            public CustomProperties(MaterialProperty[] props)");
//             sb.AppendLine("            {");
//             
//             foreach (var prop in properties)
//             {
//                 string varName = GetPropertyVariableName(prop.name);
//                 sb.AppendLine($"                {varName} = FindProperty(\"{prop.name}\", props, false);");
//             }
//             
//             sb.AppendLine("            }");
//             sb.AppendLine();
//             
//             // FindProperty辅助方法
//             sb.AppendLine("            private static MaterialProperty FindProperty(string name, MaterialProperty[] props, bool mandatory = true)");
//             sb.AppendLine("            {");
//             sb.AppendLine("                for (int i = 0; i < props.Length; i++)");
//             sb.AppendLine("                {");
//             sb.AppendLine("                    if (props[i] != null && props[i].name == name)");
//             sb.AppendLine("                        return props[i];");
//             sb.AppendLine("                }");
//             sb.AppendLine("                if (mandatory)");
//             sb.AppendLine("                    throw new ArgumentException(\"Could not find material property: \" + name);");
//             sb.AppendLine("                return null;");
//             sb.AppendLine("            }");
//             
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GenerateFoldoutVariables(StringBuilder sb, List<ShaderPropertyInfo> properties)
//         {
//             var groups = GetPropertyGroups(properties);
//             
//             sb.AppendLine();
//             sb.AppendLine("        // Foldout states");
//             
//             foreach (var group in groups.Keys)
//             {
//                 if (!string.IsNullOrEmpty(group))
//                 {
//                     string foldoutName = GetFoldoutVariableName(group);
//                     sb.AppendLine($"        private bool {foldoutName} = true;");
//                 }
//             }
//         }
//
//         private void GenerateOnGUIMethod(StringBuilder sb)
//         {
//             sb.AppendLine("        public override void OnGUI(MaterialEditor editor, MaterialProperty[] props)");
//             sb.AppendLine("        {");
//             sb.AppendLine("            FindProperties(props);");
//             sb.AppendLine("            materialEditor = editor;");
//             sb.AppendLine("            Material material = editor.target as Material;");
//             sb.AppendLine();
//             sb.AppendLine("            if (material == null) return;");
//             sb.AppendLine();
//             sb.AppendLine("            int keepRenderQueue = material.renderQueue;");
//             sb.AppendLine();
//             sb.AppendLine("            ShaderPropertiesGUI(material);");
//             sb.AppendLine();
//             sb.AppendLine("            // 保持Render Queue (除非是默认值)");
//             sb.AppendLine("            if (keepRenderQueue != 3000 && keepRenderQueue != 2000)");
//             sb.AppendLine("            {");
//             sb.AppendLine("                material.renderQueue = keepRenderQueue;");
//             sb.AppendLine("            }");
//             sb.AppendLine();
//             sb.AppendLine("            // Render Queue 编辑");
//             sb.AppendLine("            EditorGUI.BeginChangeCheck();");
//             sb.AppendLine("            int renderQueue = EditorGUILayout.IntField(\"Render Queue\", material.renderQueue);");
//             sb.AppendLine("            if (EditorGUI.EndChangeCheck())");
//             sb.AppendLine("            {");
//             sb.AppendLine("                material.renderQueue = renderQueue;");
//             sb.AppendLine("            }");
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GenerateFindPropertiesMethod(StringBuilder sb)
//         {
//             sb.AppendLine("        public void FindProperties(MaterialProperty[] props)");
//             sb.AppendLine("        {");
//             sb.AppendLine("            properties = new CustomProperties(props);");
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GenerateMaterialChangedMethod(StringBuilder sb)
//         {
//             sb.AppendLine("        public void MaterialChanged(Material material)");
//             sb.AppendLine("        {");
//             sb.AppendLine("            if (material == null)");
//             sb.AppendLine("                throw new ArgumentNullException(\"material\");");
//             sb.AppendLine();
//             sb.AppendLine("            SetMaterialKeywords(material);");
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GenerateSetKeywordsMethod(StringBuilder sb, List<ShaderPropertyInfo> properties)
//         {
//             sb.AppendLine("        public void SetMaterialKeywords(Material material)");
//             sb.AppendLine("        {");
//             
//             var toggleProperties = properties.Where(p => p.isToggle && !string.IsNullOrEmpty(p.keywordName)).ToList();
//             
//             if (toggleProperties.Count > 0)
//             {
//                 sb.AppendLine("            // 根据属性设置Shader关键字");
//                 
//                 foreach (var prop in toggleProperties)
//                 {
//                     sb.AppendLine($"            if (material.HasProperty(\"{prop.name}\"))");
//                     sb.AppendLine($"                CoreUtils.SetKeyword(material, \"{prop.keywordName}\",");
//                     sb.AppendLine($"                    material.GetFloat(\"{prop.name}\") == 1.0f);");
//                 }
//             }
//             else
//             {
//                 sb.AppendLine("            // TODO: 添加Shader关键字控制逻辑");
//             }
//             
//             sb.AppendLine("        }");
//             sb.AppendLine();
//         }
//
//         private void GenerateShaderPropertiesGUIMethod(StringBuilder sb, List<ShaderPropertyInfo> properties)
//         {
//             sb.AppendLine("        public void ShaderPropertiesGUI(Material material)");
//             sb.AppendLine("        {");
//             
//             if (generateFoldouts && groupByPrefix)
//             {
//                 var groups = GetPropertyGroups(properties);
//                 
//                 foreach (var group in groups)
//                 {
//                     if (string.IsNullOrEmpty(group.Key))
//                     {
//                         // 无分组的属性
//                         foreach (var prop in group.Value)
//                         {
//                             GeneratePropertyGUI(sb, prop, "            ");
//                         }
//                     }
//                     else
//                     {
//                         // 有分组的属性
//                         string foldoutName = GetFoldoutVariableName(group.Key);
//                         string displayName = FormatGroupName(group.Key);
//                         
//                         sb.AppendLine();
//                         sb.AppendLine($"            {foldoutName} = EditorGUILayout.Foldout({foldoutName}, \"{displayName}\", true);");
//                         sb.AppendLine($"            if ({foldoutName})");
//                         sb.AppendLine("            {");
//                         sb.AppendLine("                EditorGUI.indentLevel++;");
//                         
//                         foreach (var prop in group.Value)
//                         {
//                             GeneratePropertyGUI(sb, prop, "                ");
//                         }
//                         
//                         sb.AppendLine("                EditorGUI.indentLevel--;");
//                         sb.AppendLine("            }");
//                     }
//                 }
//             }
//             else
//             {
//                 foreach (var prop in properties)
//                 {
//                     GeneratePropertyGUI(sb, prop, "            ");
//                 }
//             }
//             
//             sb.AppendLine("        }");
//         }
//
//         private void GeneratePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string indent)
//         {
//             string varName = GetPropertyVariableName(prop.name);
//             string styleName = GetStyleVariableName(prop.name);
//             
//             sb.AppendLine();
//             sb.AppendLine($"{indent}// {prop.displayName}");
//             sb.AppendLine($"{indent}if (properties.{varName} != null)");
//             sb.AppendLine($"{indent}{{");
//             
//             // 根据属性类型生成不同的GUI代码
//             switch (prop.type)
//             {
//                 case ShaderUtil.ShaderPropertyType.TexEnv:
//                     GenerateTexturePropertyGUI(sb, prop, varName, styleName, indent + "    ");
//                     break;
//                     
//                 case ShaderUtil.ShaderPropertyType.Color:
//                     sb.AppendLine($"{indent}    materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
//                     break;
//                     
//                 case ShaderUtil.ShaderPropertyType.Vector:
//                     sb.AppendLine($"{indent}    materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
//                     break;
//                     
//                 case ShaderUtil.ShaderPropertyType.Float:
//                 case ShaderUtil.ShaderPropertyType.Range:
//                     if (prop.isToggle)
//                     {
//                         GenerateTogglePropertyGUI(sb, prop, varName, styleName, indent + "    ");
//                     }
//                     else
//                     {
//                         sb.AppendLine($"{indent}    materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
//                     }
//                     break;
//             }
//             
//             sb.AppendLine($"{indent}}}");
//         }
//
//         private void GenerateTexturePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
//         {
//             // 检查是否有对应的缩放/偏移属性或其他关联属性
//             string propNameLower = prop.name.ToLower();
//             
//             if (propNameLower.Contains("normal") || propNameLower.Contains("bump"))
//             {
//                 // 法线贴图，可能有Scale属性
//                 string scaleVarName = varName.Replace("Map", "Scale").Replace("map", "Scale");
//                 sb.AppendLine($"{indent}materialEditor.TexturePropertySingleLine(Styles.{styleName}, properties.{varName});");
//             }
//             else if (propNameLower.Contains("base") || propNameLower.Contains("diffuse") || propNameLower.Contains("albedo"))
//             {
//                 // 基础贴图，可能有颜色属性
//                 sb.AppendLine($"{indent}materialEditor.TexturePropertySingleLine(Styles.{styleName}, properties.{varName});");
//             }
//             else
//             {
//                 sb.AppendLine($"{indent}materialEditor.TexturePropertySingleLine(Styles.{styleName}, properties.{varName});");
//             }
//         }
//
//         private void GenerateTogglePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
//         {
//             if (generateKeywords && !string.IsNullOrEmpty(prop.keywordName))
//             {
//                 sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
//                 sb.AppendLine($"{indent}materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
//                 sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
//                 sb.AppendLine($"{indent}{{");
//                 sb.AppendLine($"{indent}    MaterialChanged(material);");
//                 sb.AppendLine($"{indent}}}");
//             }
//             else
//             {
//                 sb.AppendLine($"{indent}materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
//             }
//         }
//
//         private Dictionary<string, List<ShaderPropertyInfo>> GetPropertyGroups(List<ShaderPropertyInfo> properties)
//         {
//             var groups = new Dictionary<string, List<ShaderPropertyInfo>>();
//             
//             if (!groupByPrefix)
//             {
//                 groups[""] = properties;
//                 return groups;
//             }
//             
//             // 常见的分组前缀
//             var groupPrefixes = new Dictionary<string, string>
//             {
//                 { "base", "基础设置" },
//                 { "metallic", "金属/粗糙度" },
//                 { "normal", "法线" },
//                 { "bump", "法线" },
//                 { "emission", "自发光" },
//                 { "rim", "边缘光" },
//                 { "sss", "次表面散射" },
//                 { "uvlight", "UV流光" },
//                 { "cube", "环境贴图" },
//                 { "effect", "特效" },
//                 { "light", "光照" },
//                 { "specular", "高光" },
//                 { "aniso", "各向异性" },
//                 { "rain", "雨滴效果" },
//                 { "camera", "相机" },
//                 { "reflect", "反射" },
//                 { "occlusion", "AO" },
//                 { "ao", "AO" },
//             };
//             
//             foreach (var prop in properties)
//             {
//                 string propLower = prop.name.TrimStart('_').ToLower();
//                 string groupKey = "";
//                 
//                 foreach (var prefix in groupPrefixes)
//                 {
//                     if (propLower.StartsWith(prefix.Key))
//                     {
//                         groupKey = prefix.Value;
//                         break;
//                     }
//                 }
//                 
//                 if (!groups.ContainsKey(groupKey))
//                 {
//                     groups[groupKey] = new List<ShaderPropertyInfo>();
//                 }
//                 
//                 groups[groupKey].Add(prop);
//             }
//             
//             return groups;
//         }
//
//         private string GetStyleVariableName(string propertyName)
//         {
//             // _BaseMap -> baseMapText
//             string name = propertyName.TrimStart('_');
//             if (name.Length > 0)
//             {
//                 name = char.ToLower(name[0]) + name.Substring(1);
//             }
//             return name + "Text";
//         }
//
//         private string GetPropertyVariableName(string propertyName)
//         {
//             // _BaseMap -> baseMap
//             string name = propertyName.TrimStart('_');
//             if (name.Length > 0)
//             {
//                 name = char.ToLower(name[0]) + name.Substring(1);
//             }
//             return name;
//         }
//
//         private string GetFoldoutVariableName(string groupName)
//         {
//             // 基础设置 -> showBasicSettings
//             string name = groupName.Replace(" ", "").Replace("/", "");
//             return "show" + name + "Foldout";
//         }
//
//         private string FormatGroupName(string groupKey)
//         {
//             return groupKey;
//         }
//
//         private string GenerateTooltip(ShaderPropertyInfo prop)
//         {
//             if (prop.type == ShaderUtil.ShaderPropertyType.Range)
//             {
//                 return $"范围: {prop.rangeMin} - {prop.rangeMax}";
//             }
//             return "";
//         }
//
//         private string EscapeString(string str)
//         {
//             if (string.IsNullOrEmpty(str)) return "";
//             return str.Replace("\\", "\\\\").Replace("\"", "\\\"");
//         }
//
//         private void SaveGeneratedCode()
//         {
//             if (string.IsNullOrEmpty(generatedCode))
//             {
//                 EditorUtility.DisplayDialog("错误", "没有可保存的代码", "确定");
//                 return;
//             }
//             
//             string fileName = outputClassName + ".cs";
//             string fullPath = Path.Combine(outputPath, fileName);
//             
//             // 确保目录存在
//             string directory = Path.GetDirectoryName(fullPath);
//             if (!Directory.Exists(directory))
//             {
//                 Directory.CreateDirectory(directory);
//             }
//             
//             // 检查文件是否已存在
//             if (File.Exists(fullPath))
//             {
//                 if (!EditorUtility.DisplayDialog("文件已存在", 
//                     $"文件 {fileName} 已存在，是否覆盖？", "覆盖", "取消"))
//                 {
//                     return;
//                 }
//             }
//             
//             File.WriteAllText(fullPath, generatedCode, Encoding.UTF8);
//             AssetDatabase.Refresh();
//             
//             EditorUtility.DisplayDialog("成功", $"文件已保存到:\n{fullPath}", "确定");
//             
//             // 选中生成的文件
//             var asset = AssetDatabase.LoadAssetAtPath<MonoScript>(fullPath);
//             if (asset != null)
//             {
//                 Selection.activeObject = asset;
//                 EditorGUIUtility.PingObject(asset);
//             }
//         }
//     }
// }
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
    public class BY_ShaderGUIGenerator : EditorWindow
    {
        private Shader selectedShader;
        private string outputClassName = "CustomShaderGUI";
        private string outputNamespace = "UnityEditor.ShaderGraph";
        private Vector2 scrollPosition;
        private string generatedCode = "";
        private bool showPreview = false;
        private string outputPath = "Assets/Editor/";
        
        private bool groupByPrefix = false;
        private bool generateFoldouts = false;
        private bool generateKeywords = true;
        
        private enum TextureDisplayStyle
        {
            Default,
            SingleLine,
            LargeThumb
        }
        private TextureDisplayStyle textureStyle = TextureDisplayStyle.Default;
        
        private List<string> shaderKeywords = new List<string>();
        private Dictionary<string, string> propertyKeywordMap = new Dictionary<string, string>();
        private Dictionary<string, PropertyAttributeInfo> propertyAttributes = new Dictionary<string, PropertyAttributeInfo>();
        
        // 是否支持GPU Instancing
        private bool hasGPUInstancing = false;
        // 是否有Emission
        private bool hasEmission = false;
        
        // 修改 PropertyAttributeInfo 类
        private class PropertyAttributeInfo
        {
            public string attributeType;
            public string explicitKeyword;
            public string[] enumValues;
            public string[] keywordEnumKeywords;  // 新增：存储生成的关键字数组
            public bool isToggleOff;
            public bool isKeywordEnum;  // 新增
            public bool isHidden;  // 新增：标记是否隐藏
        }
        
        // 修改 ShaderPropertyInfo 类，添加枚举关键字列表
        private class ShaderPropertyInfo
        {
            public string name;
            public string displayName;
            public ShaderUtil.ShaderPropertyType type;
            public string description;
            public bool isToggle;
            public bool isToggleOff;
            public bool isEnum;
            public bool isKeywordEnum;  // 新增：区分普通Enum和KeywordEnum
            public string keywordName;
            public float rangeMin;
            public float rangeMax;
            public string[] enumNames;
            public string[] keywordEnumKeywords;  // 新增：KeywordEnum的所有关键字
            public string attributeType;
            public bool isHidden;  // 新增：标记是否隐藏
        }
        // 在类中添加一个选项
        private enum ToggleDisplayStyle
        {
            Toggle,           // 标准 Toggle（复选框在左侧）
            ToggleLeft,       // 标签在左侧，复选框在右侧
            Foldout,          // 折叠样式
            Button            // 按钮样式
        }
        private ToggleDisplayStyle toggleStyle = ToggleDisplayStyle.Toggle;


        [MenuItem("Tools/TempByAI/Shader GUI Generator", false, 100)]
        public static void ShowWindow()
        {
            var window = GetWindow<BY_ShaderGUIGenerator>("Shader GUI Generator");
            window.minSize = new Vector2(550, 750);
        }

        private void OnGUI()
        {
            EditorGUILayout.Space(10);
            EditorGUILayout.LabelField("BY Shader GUI 自动生成工具", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);
            
            DrawLine();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("选择Shader:", GUILayout.Width(80));
            EditorGUI.BeginChangeCheck();
            selectedShader = (Shader)EditorGUILayout.ObjectField(selectedShader, typeof(Shader), false);
            if (EditorGUI.EndChangeCheck() && selectedShader != null)
            {
                ParseShaderKeywords();
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(5);
            
            // 显示Shader特性
            if (selectedShader != null)
            {
                EditorGUILayout.BeginHorizontal();
                if (hasGPUInstancing)
                {
                    EditorGUILayout.LabelField("✓ GPU Instancing", EditorStyles.miniLabel, GUILayout.Width(120));
                }
                if (hasEmission)
                {
                    EditorGUILayout.LabelField("✓ Emission", EditorStyles.miniLabel, GUILayout.Width(80));
                }
                EditorGUILayout.EndHorizontal();
                
                if (shaderKeywords.Count > 0)
                {
                    EditorGUILayout.LabelField($"检测到 {shaderKeywords.Count} 个Shader关键字:", EditorStyles.miniLabel);
                    EditorGUI.indentLevel++;
                    string keywordsPreview = string.Join(", ", shaderKeywords.Take(15));
                    if (shaderKeywords.Count > 15) keywordsPreview += "...";
                    EditorGUILayout.LabelField(keywordsPreview, EditorStyles.wordWrappedMiniLabel);
                    EditorGUI.indentLevel--;
                }
                EditorGUILayout.Space(5);
            }
            
            EditorGUILayout.LabelField("输出设置", EditorStyles.boldLabel);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("类名:", GUILayout.Width(80));
            outputClassName = EditorGUILayout.TextField(outputClassName);
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("命名空间:", GUILayout.Width(80));
            outputNamespace = EditorGUILayout.TextField(outputNamespace);
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("输出路径:", GUILayout.Width(80));
            outputPath = EditorGUILayout.TextField(outputPath);
            if (GUILayout.Button("浏览", GUILayout.Width(50)))
            {
                string path = EditorUtility.OpenFolderPanel("选择输出目录", outputPath, "");
                if (!string.IsNullOrEmpty(path))
                {
                    outputPath = "Assets" + path.Substring(Application.dataPath.Length) + "/";
                }
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(5);
            
            EditorGUILayout.LabelField("生成选项", EditorStyles.boldLabel);
            groupByPrefix = EditorGUILayout.Toggle("按前缀分组", groupByPrefix);
            generateFoldouts = EditorGUILayout.Toggle("生成折叠面板", generateFoldouts);
            generateKeywords = EditorGUILayout.Toggle("生成Keyword控制", generateKeywords);
            
            // 在 "生成选项" 部分添加
            EditorGUILayout.Space(5);
            EditorGUILayout.LabelField("Toggle显示样式", EditorStyles.boldLabel);
            toggleStyle = (ToggleDisplayStyle)EditorGUILayout.EnumPopup("样式", toggleStyle);

            EditorGUI.indentLevel++;
            switch (toggleStyle)
            {
                case ToggleDisplayStyle.Toggle:
                    EditorGUILayout.HelpBox("标准复选框样式，复选框在左侧", MessageType.Info);
                    break;
                case ToggleDisplayStyle.ToggleLeft:
                    EditorGUILayout.HelpBox("标签在左侧，复选框在右侧", MessageType.Info);
                    break;
                case ToggleDisplayStyle.Foldout:
                    EditorGUILayout.HelpBox("折叠箭头样式", MessageType.Info);
                    break;
                case ToggleDisplayStyle.Button:
                    EditorGUILayout.HelpBox("按钮切换样式", MessageType.Info);
                    break;
            }
            EditorGUI.indentLevel--;
            
            EditorGUILayout.Space(5);
            EditorGUILayout.LabelField("贴图显示样式", EditorStyles.boldLabel);
            textureStyle = (TextureDisplayStyle)EditorGUILayout.EnumPopup("样式", textureStyle);
            
            EditorGUI.indentLevel++;
            switch (textureStyle)
            {
                case TextureDisplayStyle.Default:
                    EditorGUILayout.HelpBox("使用ShaderProperty，显示大缩略图在右侧（推荐）", MessageType.Info);
                    break;
                case TextureDisplayStyle.SingleLine:
                    EditorGUILayout.HelpBox("使用TexturePropertySingleLine，显示小缩略图在左侧，紧凑布局", MessageType.Info);
                    break;
                case TextureDisplayStyle.LargeThumb:
                    EditorGUILayout.HelpBox("使用TextureProperty，显示大缩略图并包含Tiling/Offset", MessageType.Info);
                    break;
            }
            EditorGUI.indentLevel--;
            
            EditorGUILayout.Space(10);
            DrawLine();
            
            EditorGUILayout.BeginHorizontal();
            
            GUI.enabled = selectedShader != null;
            
            if (GUILayout.Button("解析Shader", GUILayout.Height(30)))
            {
                ParseShaderKeywords();
                showPreview = false;
            }
            
            if (GUILayout.Button("预览代码", GUILayout.Height(30)))
            {
                if (shaderKeywords.Count == 0 && propertyAttributes.Count == 0)
                {
                    ParseShaderKeywords();
                }
                generatedCode = GenerateShaderGUICode();
                showPreview = true;
            }
            
            if (GUILayout.Button("生成并保存", GUILayout.Height(30)))
            {
                if (shaderKeywords.Count == 0 && propertyAttributes.Count == 0)
                {
                    ParseShaderKeywords();
                }
                generatedCode = GenerateShaderGUICode();
                SaveGeneratedCode();
            }
            
            GUI.enabled = true;
            
            if (GUILayout.Button("复制到剪贴板", GUILayout.Height(30)))
            {
                if (!string.IsNullOrEmpty(generatedCode))
                {
                    EditorGUIUtility.systemCopyBuffer = generatedCode;
                    EditorUtility.DisplayDialog("成功", "代码已复制到剪贴板", "确定");
                }
            }
            
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(10);
            
            if (selectedShader != null && propertyKeywordMap.Count > 0 && !showPreview)
            {
                EditorGUILayout.LabelField($"属性-关键字映射 ({propertyKeywordMap.Count}个)", EditorStyles.boldLabel);
                scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.Height(250));
                
                EditorGUILayout.BeginHorizontal("box");
                EditorGUILayout.LabelField("属性名", EditorStyles.boldLabel, GUILayout.Width(180));
                EditorGUILayout.LabelField("类型", EditorStyles.boldLabel, GUILayout.Width(100));
                EditorGUILayout.LabelField("关键字", EditorStyles.boldLabel);
                EditorGUILayout.EndHorizontal();
                
                foreach (var kvp in propertyKeywordMap)
                {
                    EditorGUILayout.BeginHorizontal("box");
                    EditorGUILayout.LabelField(kvp.Key, GUILayout.Width(180));
                    
                    string attrType = "Auto";
                    if (propertyAttributes.ContainsKey(kvp.Key))
                    {
                        var attr = propertyAttributes[kvp.Key];
                        attrType = attr.attributeType;
                        if (attr.isToggleOff) attrType += " (Off)";
                    }
                    EditorGUILayout.LabelField(attrType, GUILayout.Width(100));
                    
                    EditorGUILayout.LabelField(kvp.Value, EditorStyles.boldLabel);
                    EditorGUILayout.EndHorizontal();
                }
                EditorGUILayout.EndScrollView();
                
                DrawLine();
            }
            
            if (showPreview && !string.IsNullOrEmpty(generatedCode))
            {
                EditorGUILayout.LabelField("代码预览", EditorStyles.boldLabel);
                scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
                
                var codeStyle = new GUIStyle(EditorStyles.textArea);
                codeStyle.wordWrap = false;
                
                EditorGUILayout.TextArea(generatedCode, codeStyle, GUILayout.ExpandHeight(true));
                EditorGUILayout.EndScrollView();
            }
            
            if (selectedShader != null && !showPreview && propertyKeywordMap.Count == 0)
            {
                EditorGUILayout.LabelField("Shader属性列表", EditorStyles.boldLabel);
                scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, GUILayout.ExpandHeight(true));
                DrawShaderProperties();
                EditorGUILayout.EndScrollView();
            }
        }

        private void DrawLine()
        {
            EditorGUILayout.Space(5);
            var rect = EditorGUILayout.GetControlRect(false, 1);
            EditorGUI.DrawRect(rect, new Color(0.5f, 0.5f, 0.5f, 1));
            EditorGUILayout.Space(5);
        }

        private void DrawShaderProperties()
        {
            if (selectedShader == null) return;
            
            int propertyCount = ShaderUtil.GetPropertyCount(selectedShader);
            
            EditorGUILayout.LabelField($"共 {propertyCount} 个属性", EditorStyles.miniLabel);
            EditorGUILayout.Space(5);
            
            for (int i = 0; i < propertyCount; i++)
            {
                string name = ShaderUtil.GetPropertyName(selectedShader, i);
                string desc = ShaderUtil.GetPropertyDescription(selectedShader, i);
                var type = ShaderUtil.GetPropertyType(selectedShader, i);
                // 检查是否隐藏
                bool isHidden = propertyAttributes.ContainsKey(name) && propertyAttributes[name].isHidden;
                
                EditorGUILayout.BeginHorizontal("box");
                // 隐藏的属性显示灰色
                if (isHidden)
                {
                    GUI.color = Color.gray;
                    EditorGUILayout.LabelField("[Hidden] " + name, GUILayout.Width(200));
                }
                else
                {
                    EditorGUILayout.LabelField(name, GUILayout.Width(200));
                }
                EditorGUILayout.LabelField(type.ToString(), GUILayout.Width(80));
                EditorGUILayout.LabelField(desc);
                GUI.color = Color.white;
                EditorGUILayout.EndHorizontal();
            }
        }

        private void ParseShaderKeywords()
        {
            shaderKeywords.Clear();
            propertyKeywordMap.Clear();
            propertyAttributes.Clear();
            hasGPUInstancing = false;
            hasEmission = false;
            
            if (selectedShader == null) return;
            
            string shaderPath = AssetDatabase.GetAssetPath(selectedShader);
            if (string.IsNullOrEmpty(shaderPath)) return;
            
            string shaderSource = "";
            try
            {
                shaderSource = File.ReadAllText(shaderPath);
                shaderSource += ParseIncludedFiles(shaderPath, shaderSource);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"无法读取Shader文件: {e.Message}");
                return;
            }
            
            // 检测Shader特性
            DetectShaderFeatures(shaderSource);
            
            // 解析shader_feature中的关键字
            ExtractKeywordsFromSource(shaderSource);
            
            // 解析Properties块中的属性Attribute
            ParsePropertyAttributes(shaderSource);
            
            // 建立属性到关键字的映射
            BuildPropertyKeywordMapping();
            
            Debug.Log($"解析完成: 找到 {shaderKeywords.Count} 个关键字, {propertyAttributes.Count} 个Toggle/Enum属性, {propertyKeywordMap.Count} 个属性映射, GPU Instancing: {hasGPUInstancing}");
        }

        /// <summary>
        /// 检测Shader特性（GPU Instancing, Emission等）
        /// </summary>
        private void DetectShaderFeatures(string shaderSource)
        {
            // 检测 #pragma multi_compile_instancing
            hasGPUInstancing = Regex.IsMatch(shaderSource, @"#pragma\s+multi_compile_instancing", RegexOptions.Multiline);
            
            // 检测 Emission（检查是否有_EmissionColor或_EmissionMap属性，或者有_EMISSION关键字）
            hasEmission = Regex.IsMatch(shaderSource, @"_Emission(Color|Map)", RegexOptions.IgnoreCase) ||
                         Regex.IsMatch(shaderSource, @"#pragma\s+shader_feature.*_EMISSION", RegexOptions.Multiline);
            
            if (hasGPUInstancing)
            {
                Debug.Log("检测到: #pragma multi_compile_instancing");
            }
            if (hasEmission)
            {
                Debug.Log("检测到: Emission支持");
            }
        }

        // 修改 ParsePropertyAttributes 方法中的 KeywordEnum 部分
        private void ParsePropertyAttributes(string shaderSource)
        {
            var propertiesMatch =
                Regex.Match(shaderSource, @"Properties\s*\{([\s\S]*?)\n\s*\}", RegexOptions.Multiline);
            if (!propertiesMatch.Success)
            {
                Debug.LogWarning("未找到Properties块");
                return;
            }

            string propertiesBlock = propertiesMatch.Groups[1].Value;
            string[] lines = propertiesBlock.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);

            foreach (string line in lines)
            {
                string trimmedLine = line.Trim();
                if (string.IsNullOrEmpty(trimmedLine) || trimmedLine.StartsWith("//"))
                    continue;

                var propNameMatch = Regex.Match(trimmedLine, @"(_[A-Za-z][A-Za-z0-9_]*)\s*\(\s*""[^""]*""\s*,");
                if (!propNameMatch.Success)
                    continue;

                string propName = propNameMatch.Groups[1].Value;
                
                // ===== 新增：检测 [HideInInspector] =====
                bool isHidden = Regex.IsMatch(trimmedLine, @"\[HideInInspector\]", RegexOptions.IgnoreCase);
                if (isHidden)
                {
                    // 如果已经有该属性的记录，更新它；否则创建新记录
                    if (!propertyAttributes.ContainsKey(propName))
                    {
                        propertyAttributes[propName] = new PropertyAttributeInfo();
                    }
                    propertyAttributes[propName].isHidden = true;
                    Debug.Log($"找到 [HideInInspector] -> {propName}");
                    // 注意：不要 continue，因为可能还有其他属性标记需要解析
                }
                // ===== 新增结束 =====

                // [Toggle(_KEYWORD)]
                var toggleWithKeywordMatch = Regex.Match(trimmedLine, @"\[Toggle\s*\(\s*([A-Z_][A-Z0-9_]*)\s*\)\s*\]",
                    RegexOptions.IgnoreCase);
                if (toggleWithKeywordMatch.Success)
                {
                    string keyword = toggleWithKeywordMatch.Groups[1].Value.ToUpper();
                    propertyAttributes[propName] = new PropertyAttributeInfo
                    {
                        attributeType = "Toggle",
                        explicitKeyword = keyword,
                        isToggleOff = false,
                        isKeywordEnum = false
                    };
                    Debug.Log($"找到 [Toggle({keyword})] -> {propName}");
                    continue;
                }

                // [ToggleOff]
                if (Regex.IsMatch(trimmedLine, @"\[ToggleOff\s*\]", RegexOptions.IgnoreCase))
                {
                    propertyAttributes[propName] = new PropertyAttributeInfo
                    {
                        attributeType = "ToggleOff",
                        explicitKeyword = null,
                        isToggleOff = true,
                        isKeywordEnum = false
                    };
                    Debug.Log($"找到 [ToggleOff] -> {propName}");
                    continue;
                }

                // [Toggle]
                if (Regex.IsMatch(trimmedLine, @"\[Toggle\s*\]", RegexOptions.IgnoreCase))
                {
                    propertyAttributes[propName] = new PropertyAttributeInfo
                    {
                        attributeType = "Toggle",
                        explicitKeyword = null,
                        isToggleOff = false,
                        isKeywordEnum = false
                    };
                    Debug.Log($"找到 [Toggle] -> {propName}");
                    continue;
                }

                // [KeywordEnum(A, B, C)] - 关键修改
                var keywordEnumMatch = Regex.Match(trimmedLine, @"\[KeywordEnum\s*\(\s*([^)]+)\s*\)\s*\]",
                    RegexOptions.IgnoreCase);
                if (keywordEnumMatch.Success)
                {
                    string enumValues = keywordEnumMatch.Groups[1].Value;
                    var values = enumValues.Split(',').Select(v => v.Trim()).ToArray();

                    // 生成关键字数组：属性名大写_枚举值大写
                    // 例如 _Mode 的枚举值 Normal, Warm, Cool 
                    // 生成 _MODE_NORMAL, _MODE_WARM, _MODE_COOL
                    string propUpper = propName.ToUpper();
                    var keywords = values.Select(v => $"{propUpper}_{v.ToUpper()}").ToArray();

                    propertyAttributes[propName] = new PropertyAttributeInfo
                    {
                        attributeType = "KeywordEnum",
                        enumValues = values,
                        keywordEnumKeywords = keywords,
                        isToggleOff = false,
                        isKeywordEnum = true
                    };

                    Debug.Log($"找到 [KeywordEnum({enumValues})] -> {propName}");
                    Debug.Log($"  生成关键字: {string.Join(", ", keywords)}");
                    continue;
                }
            }
        }

        private string ParseIncludedFiles(string mainShaderPath, string shaderSource)
        {
            StringBuilder includedContent = new StringBuilder();
            
            var includePattern = new Regex(@"#include\s+""([^""]+)""", RegexOptions.Multiline);
            var matches = includePattern.Matches(shaderSource);
            
            string shaderDirectory = Path.GetDirectoryName(mainShaderPath);
            
            foreach (Match match in matches)
            {
                string includePath = match.Groups[1].Value;
                
                string[] possiblePaths = new string[]
                {
                    Path.Combine(shaderDirectory, includePath),
                    Path.Combine("Assets", includePath),
                    includePath
                };
                
                foreach (string tryPath in possiblePaths)
                {
                    if (File.Exists(tryPath))
                    {
                        try
                        {
                            includedContent.AppendLine(File.ReadAllText(tryPath));
                        }
                        catch { }
                        break;
                    }
                }
            }
            
            return includedContent.ToString();
        }

        private void ExtractKeywordsFromSource(string source)
        {
            var pragmaPatterns = new string[]
            {
                @"#pragma\s+shader_feature(?:_local)?\s+(.+)",
                @"#pragma\s+multi_compile(?:_local)?\s+(.+)"
            };
            
            foreach (var pattern in pragmaPatterns)
            {
                var regex = new Regex(pattern, RegexOptions.Multiline);
                var matches = regex.Matches(source);
                
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
                        if (!string.IsNullOrEmpty(kw) && kw != "_" && 
                            !kw.StartsWith("_ADDITIONAL_LIGHTS") &&
                            !kw.StartsWith("_MAIN_LIGHT") &&
                            !shaderKeywords.Contains(kw))
                        {
                            shaderKeywords.Add(kw);
                            Debug.Log($"找到关键字: {kw}");
                        }
                    }
                }
            }
        }

        // 修改 BuildPropertyKeywordMapping 方法中的 KeywordEnum 部分
        private void BuildPropertyKeywordMapping()
        {
            if (selectedShader == null) return;

            int propertyCount = ShaderUtil.GetPropertyCount(selectedShader);

            for (int i = 0; i < propertyCount; i++)
            {
                string propName = ShaderUtil.GetPropertyName(selectedShader, i);
                var propType = ShaderUtil.GetPropertyType(selectedShader, i);

                if (propType != ShaderUtil.ShaderPropertyType.Float &&
                    propType != ShaderUtil.ShaderPropertyType.Range)
                {
                    continue;
                }

                if (propertyAttributes.ContainsKey(propName))
                {
                    var attr = propertyAttributes[propName];

                    // Toggle with explicit keyword
                    if (!string.IsNullOrEmpty(attr.explicitKeyword))
                    {
                        if (shaderKeywords.Contains(attr.explicitKeyword))
                        {
                            propertyKeywordMap[propName] = attr.explicitKeyword;
                            Debug.Log($"映射(明确指定): {propName} -> {attr.explicitKeyword}");
                        }
                        else
                        {
                            propertyKeywordMap[propName] = attr.explicitKeyword;
                            Debug.LogWarning($"映射(未验证): {propName} -> {attr.explicitKeyword} (关键字未在shader_feature中找到)");
                        }

                        continue;
                    }

                    // ToggleOff
                    if (attr.isToggleOff)
                    {
                        string keyword = propName.ToUpper() + "_OFF";

                        if (shaderKeywords.Contains(keyword))
                        {
                            propertyKeywordMap[propName] = keyword;
                            Debug.Log($"映射(ToggleOff): {propName} -> {keyword}");
                        }
                        else
                        {
                            string matched = FindMatchingKeywordWithSuffix(propName, "_OFF");
                            if (!string.IsNullOrEmpty(matched))
                            {
                                propertyKeywordMap[propName] = matched;
                                Debug.Log($"映射(ToggleOff智能匹配): {propName} -> {matched}");
                            }
                        }

                        continue;
                    }

                    // Toggle without explicit keyword
                    if (attr.attributeType == "Toggle" && !attr.isKeywordEnum)
                    {
                        string matched = FindMatchingKeywordForToggle(propName);
                        if (!string.IsNullOrEmpty(matched))
                        {
                            propertyKeywordMap[propName] = matched;
                            Debug.Log($"映射(Toggle智能匹配): {propName} -> {matched}");
                        }

                        continue;
                    }

                    // KeywordEnum - 关键修改
                    if (attr.isKeywordEnum && attr.keywordEnumKeywords != null && attr.keywordEnumKeywords.Length > 0)
                    {
                        // 对于 KeywordEnum，存储第一个关键字作为标识，完整列表在属性中
                        // 验证关键字是否存在于shader中
                        bool anyFound = false;
                        foreach (var keyword in attr.keywordEnumKeywords)
                        {
                            if (shaderKeywords.Contains(keyword))
                            {
                                anyFound = true;
                                break;
                            }
                        }

                        if (anyFound)
                        {
                            // 使用特殊格式存储，表示这是一个KeywordEnum
                            propertyKeywordMap[propName] = string.Join("|", attr.keywordEnumKeywords);
                            Debug.Log(
                                $"映射(KeywordEnum): {propName} -> [{string.Join(", ", attr.keywordEnumKeywords)}]");
                        }
                        else
                        {
                            // 即使未在shader_feature中找到，也添加映射（可能是动态使用的）
                            propertyKeywordMap[propName] = string.Join("|", attr.keywordEnumKeywords);
                            Debug.LogWarning(
                                $"映射(KeywordEnum未验证): {propName} -> [{string.Join(", ", attr.keywordEnumKeywords)}] (关键字未在shader_feature中找到)");
                        }

                        continue;
                    }
                }
            }
        }

        private string FindMatchingKeywordForToggle(string propertyName)
        {
            string propCore = ExtractPropertyCore(propertyName);
            string[] suffixes = new string[] { "_ON", "_OPEN", "_ENABLE", "" };
            
            foreach (var suffix in suffixes)
            {
                string directKeyword = "_" + propCore + suffix;
                if (shaderKeywords.Contains(directKeyword))
                {
                    return directKeyword;
                }
                
                string noUnderscoreKeyword = propCore + suffix;
                if (shaderKeywords.Contains(noUnderscoreKeyword))
                {
                    return noUnderscoreKeyword;
                }
            }
            
            foreach (var keyword in shaderKeywords)
            {
                string keywordCore = ExtractKeywordCore(keyword);
                
                if (propCore.Equals(keywordCore, StringComparison.OrdinalIgnoreCase) ||
                    propCore.Replace("_", "").Equals(keywordCore.Replace("_", ""), StringComparison.OrdinalIgnoreCase))
                {
                    if (!keyword.EndsWith("_OFF"))
                    {
                        return keyword;
                    }
                }
            }
            
            return null;
        }

        private string FindMatchingKeywordWithSuffix(string propertyName, string suffix)
        {
            string propCore = ExtractPropertyCore(propertyName);
            
            foreach (var keyword in shaderKeywords)
            {
                if (!keyword.EndsWith(suffix))
                    continue;
                
                string keywordCore = ExtractKeywordCore(keyword);
                
                if (propCore.Equals(keywordCore, StringComparison.OrdinalIgnoreCase) ||
                    propCore.Replace("_", "").Equals(keywordCore.Replace("_", ""), StringComparison.OrdinalIgnoreCase))
                {
                    return keyword;
                }
            }
            
            return null;
        }

        private string ExtractPropertyCore(string propertyName)
        {
            string name = propertyName.TrimStart('_');
            
            string[] suffixes = new string[] 
            { 
                "Open", "Enable", "Use", "On", "Set", "Active", "Toggle", "Switch",
                "Close", "Disable", "Off"
            };
            
            foreach (var suffix in suffixes)
            {
                if (name.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
                {
                    name = name.Substring(0, name.Length - suffix.Length);
                    break;
                }
            }
            
            return name.ToUpper();
        }

        private string ExtractKeywordCore(string keyword)
        {
            string core = keyword.TrimStart('_');
            
            string[] suffixes = new string[] { "_ON", "_OFF", "_OPEN", "_ENABLE", "_CLOSE", "_DISABLE" };
            foreach (var suffix in suffixes)
            {
                if (core.EndsWith(suffix))
                {
                    core = core.Substring(0, core.Length - suffix.Length);
                    break;
                }
            }
            
            return core;
        }

        // 修改 GetShaderProperties 方法
        private List<ShaderPropertyInfo> GetShaderProperties()
        {
            var properties = new List<ShaderPropertyInfo>();

            if (selectedShader == null) return properties;

            int propertyCount = ShaderUtil.GetPropertyCount(selectedShader);

            for (int i = 0; i < propertyCount; i++)
            {
                string propName = ShaderUtil.GetPropertyName(selectedShader, i);
        
                // ===== 新增：检查是否隐藏 =====
                bool isHidden = false;
                if (propertyAttributes.ContainsKey(propName))
                {
                    isHidden = propertyAttributes[propName].isHidden;
                }
                // 跳过隐藏的属性
                if (isHidden)
                {
                    Debug.Log($"跳过隐藏属性: {propName}");
                    continue;
                }
                // ===== 新增结束 =====
                
                var prop = new ShaderPropertyInfo
                {
                    name = ShaderUtil.GetPropertyName(selectedShader, i),
                    displayName = ShaderUtil.GetPropertyDescription(selectedShader, i),
                    type = ShaderUtil.GetPropertyType(selectedShader, i),
                };

                // 处理关键字映射
                if (propertyKeywordMap.ContainsKey(prop.name))
                {
                    string keywordValue = propertyKeywordMap[prop.name];
                    // 检查是否是 KeywordEnum（包含 | 分隔符）
                    if (keywordValue.Contains("|"))
                    {
                        prop.keywordEnumKeywords = keywordValue.Split('|');
                        prop.keywordName = null; // KeywordEnum 不使用单一关键字
                    }
                    else
                    {
                        prop.keywordName = keywordValue;
                    }
                }

                if (propertyAttributes.ContainsKey(prop.name))
                {
                    var attr = propertyAttributes[prop.name];
                    prop.attributeType = attr.attributeType;
                    prop.isToggle = attr.attributeType == "Toggle" || attr.attributeType == "ToggleOff";
                    prop.isToggleOff = attr.isToggleOff;
                    prop.isKeywordEnum = attr.isKeywordEnum;
                    prop.isEnum = attr.attributeType == "Enum" || attr.attributeType == "KeywordEnum";
                    prop.enumNames = attr.enumValues;

                    if (attr.isKeywordEnum)
                    {
                        prop.keywordEnumKeywords = attr.keywordEnumKeywords;
                    }
                }
                else
                {
                    prop.isToggle = !string.IsNullOrEmpty(prop.keywordName);
                }

                if (prop.type == ShaderUtil.ShaderPropertyType.Range)
                {
                    prop.rangeMin = ShaderUtil.GetRangeLimits(selectedShader, i, 1);
                    prop.rangeMax = ShaderUtil.GetRangeLimits(selectedShader, i, 2);
                }

                prop.description = GeneratePropertyDescription(prop.name, prop.displayName);

                properties.Add(prop);
            }

            return properties;
        }

        private string GeneratePropertyDescription(string name, string displayName)
        {
            if (!string.IsNullOrEmpty(displayName) && displayName != name)
            {
                return displayName;
            }
            
            string desc = name.TrimStart('_');
            desc = Regex.Replace(desc, "(\\B[A-Z])", " $1");
            return desc;
        }

        private string GenerateShaderGUICode()
        {
            if (selectedShader == null) return "";
            
            var properties = GetShaderProperties();
            var sb = new StringBuilder();
            
            sb.AppendLine("using System;");
            sb.AppendLine("using UnityEngine;");
            sb.AppendLine("using UnityEngine.Rendering;");
            sb.AppendLine();
            
            if (!string.IsNullOrEmpty(outputNamespace))
            {
                sb.AppendLine($"namespace {outputNamespace}");
                sb.AppendLine("{");
            }
            
            string indent = string.IsNullOrEmpty(outputNamespace) ? "" : "    ";
            
            sb.AppendLine($"{indent}public class {outputClassName} : ShaderGUI");
            sb.AppendLine($"{indent}{{");
            
            GenerateStylesClass(sb, properties, indent + "    ");
            GeneratePropertiesStruct(sb, properties, indent + "    ");
            
            sb.AppendLine($"{indent}    private CustomProperties properties;");
            sb.AppendLine($"{indent}    private MaterialEditor materialEditor;");
            
            if (generateFoldouts)
            {
                GenerateFoldoutVariables(sb, properties, indent + "    ");
            }
            
            sb.AppendLine();
            
            GenerateOnGUIMethod(sb, indent + "    ");
            GenerateFindPropertiesMethod(sb, indent + "    ");
            GenerateMaterialChangedMethod(sb, indent + "    ");
            
            if (generateKeywords)
            {
                GenerateSetKeywordsMethod(sb, properties, indent + "    ");
            }
            
            GenerateShaderPropertiesGUIMethod(sb, properties, indent + "    ");
            
            sb.AppendLine($"{indent}}}");
            
            if (!string.IsNullOrEmpty(outputNamespace))
            {
                sb.AppendLine("}");
            }
            
            return sb.ToString();
        }

        private void GenerateStylesClass(StringBuilder sb, List<ShaderPropertyInfo> properties, string indent)
        {
            sb.AppendLine($"{indent}private static class Styles");
            sb.AppendLine($"{indent}{{");
            
            foreach (var prop in properties)
            {
                string varName = GetStyleVariableName(prop.name);
                string description = EscapeString(prop.description);
                string tooltip = EscapeString(GenerateTooltip(prop));
                
                if (string.IsNullOrEmpty(tooltip))
                {
                    sb.AppendLine($"{indent}    public static GUIContent {varName} = new GUIContent(\"{description}\");");
                }
                else
                {
                    sb.AppendLine($"{indent}    public static GUIContent {varName} = new GUIContent(\"{description}\", \"{tooltip}\");");
                }
            }
            
            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        private void GeneratePropertiesStruct(StringBuilder sb, List<ShaderPropertyInfo> properties, string indent)
        {
            sb.AppendLine($"{indent}private struct CustomProperties");
            sb.AppendLine($"{indent}{{");
            
            foreach (var prop in properties)
            {
                string varName = GetPropertyVariableName(prop.name);
                sb.AppendLine($"{indent}    public MaterialProperty {varName};");
            }
            
            sb.AppendLine();
            sb.AppendLine($"{indent}    public CustomProperties(MaterialProperty[] props)");
            sb.AppendLine($"{indent}    {{");
            
            foreach (var prop in properties)
            {
                string varName = GetPropertyVariableName(prop.name);
                sb.AppendLine($"{indent}        {varName} = FindProperty(\"{prop.name}\", props, false);");
            }
            
            sb.AppendLine($"{indent}    }}");
            sb.AppendLine();
            
            sb.AppendLine($"{indent}    private static MaterialProperty FindProperty(string name, MaterialProperty[] props, bool mandatory = true)");
            sb.AppendLine($"{indent}    {{");
            sb.AppendLine($"{indent}        for (int i = 0; i < props.Length; i++)");
            sb.AppendLine($"{indent}        {{");
            sb.AppendLine($"{indent}            if (props[i] != null && props[i].name == name)");
            sb.AppendLine($"{indent}                return props[i];");
            sb.AppendLine($"{indent}        }}");
            sb.AppendLine($"{indent}        if (mandatory)");
            sb.AppendLine($"{indent}            throw new ArgumentException(\"Could not find material property: \" + name);");
            sb.AppendLine($"{indent}        return null;");
            sb.AppendLine($"{indent}    }}");
            
            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        private void GenerateFoldoutVariables(StringBuilder sb, List<ShaderPropertyInfo> properties, string indent)
        {
            var groups = GetPropertyGroups(properties);
            
            sb.AppendLine();
            sb.AppendLine($"{indent}// Foldout states");
            
            foreach (var group in groups.Keys)
            {
                if (!string.IsNullOrEmpty(group))
                {
                    string foldoutName = GetFoldoutVariableName(group);
                    sb.AppendLine($"{indent}private bool {foldoutName} = true;");
                }
            }
        }

        private void GenerateOnGUIMethod(StringBuilder sb, string indent)
        {
            sb.AppendLine($"{indent}public override void OnGUI(MaterialEditor editor, MaterialProperty[] props)");
            sb.AppendLine($"{indent}{{");
            sb.AppendLine($"{indent}    FindProperties(props);");
            sb.AppendLine($"{indent}    materialEditor = editor;");
            sb.AppendLine($"{indent}    Material material = editor.target as Material;");
            sb.AppendLine();
            sb.AppendLine($"{indent}    if (material == null) return;");
            sb.AppendLine();
            sb.AppendLine($"{indent}    int keepRenderQueue = material.renderQueue;");
            sb.AppendLine();
            sb.AppendLine($"{indent}    ShaderPropertiesGUI(material);");
            sb.AppendLine();
            
            // Emission处理（如果有的话）
            if (hasEmission)
            {
                sb.AppendLine($"{indent}    // Emission");
                sb.AppendLine($"{indent}    if (editor.EmissionEnabledProperty())");
                sb.AppendLine($"{indent}    {{");
                sb.AppendLine($"{indent}        material.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;");
                sb.AppendLine($"{indent}    }}");
                sb.AppendLine();
            }
            
            sb.AppendLine($"{indent}    // 保持Render Queue (除非是默认值)");
            sb.AppendLine($"{indent}    if (keepRenderQueue != 3000 && keepRenderQueue != 2000)");
            sb.AppendLine($"{indent}    {{");
            sb.AppendLine($"{indent}        material.renderQueue = keepRenderQueue;");
            sb.AppendLine($"{indent}    }}");
            sb.AppendLine();
            sb.AppendLine($"{indent}    // Render Queue 编辑");
            sb.AppendLine($"{indent}    EditorGUI.BeginChangeCheck();");
            sb.AppendLine($"{indent}    int renderQueue = EditorGUILayout.IntField(\"Render Queue\", material.renderQueue);");
            sb.AppendLine($"{indent}    if (EditorGUI.EndChangeCheck())");
            sb.AppendLine($"{indent}    {{");
            sb.AppendLine($"{indent}        material.renderQueue = renderQueue;");
            sb.AppendLine($"{indent}    }}");
            
            // GPU Instancing
            if (hasGPUInstancing)
            {
                sb.AppendLine();
                sb.AppendLine($"{indent}    // GPU Instancing");
                sb.AppendLine($"{indent}    editor.EnableInstancingField();");
            }
            
            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        private void GenerateFindPropertiesMethod(StringBuilder sb, string indent)
        {
            sb.AppendLine($"{indent}public void FindProperties(MaterialProperty[] props)");
            sb.AppendLine($"{indent}{{");
            sb.AppendLine($"{indent}    properties = new CustomProperties(props);");
            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        private void GenerateMaterialChangedMethod(StringBuilder sb, string indent)
        {
            sb.AppendLine($"{indent}public void MaterialChanged(Material material)");
            sb.AppendLine($"{indent}{{");
            sb.AppendLine($"{indent}    if (material == null)");
            sb.AppendLine($"{indent}        throw new ArgumentNullException(\"material\");");
            sb.AppendLine();
            sb.AppendLine($"{indent}    SetMaterialKeywords(material);");
            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        // 修改 GenerateSetKeywordsMethod 方法
        private void GenerateSetKeywordsMethod(StringBuilder sb, List<ShaderPropertyInfo> properties, string indent)
        {
            sb.AppendLine($"{indent}public void SetMaterialKeywords(Material material)");
            sb.AppendLine($"{indent}{{");

            var toggleProperties = properties.Where(p => !string.IsNullOrEmpty(p.keywordName) && !p.isKeywordEnum)
                .ToList();
            var keywordEnumProperties = properties.Where(p =>
                p.isKeywordEnum && p.keywordEnumKeywords != null && p.keywordEnumKeywords.Length > 0).ToList();

            if (toggleProperties.Count > 0 || keywordEnumProperties.Count > 0)
            {
                sb.AppendLine($"{indent}    // 根据属性设置Shader关键字");

                // 处理普通 Toggle 关键字
                foreach (var prop in toggleProperties)
                {
                    bool isToggleOff = prop.isToggleOff || prop.keywordName.EndsWith("_OFF");
                    string condition = isToggleOff ? "== 0.0f" : "== 1.0f";

                    sb.AppendLine($"{indent}    if (material.HasProperty(\"{prop.name}\"))");
                    sb.AppendLine($"{indent}        CoreUtils.SetKeyword(material, \"{prop.keywordName}\",");
                    sb.AppendLine($"{indent}            material.GetFloat(\"{prop.name}\") {condition});");
                }

                // 处理 KeywordEnum 关键字
                if (keywordEnumProperties.Count > 0)
                {
                    sb.AppendLine();
                    sb.AppendLine($"{indent}    // KeywordEnum 关键字处理");

                    foreach (var prop in keywordEnumProperties)
                    {
                        sb.AppendLine();
                        sb.AppendLine($"{indent}    // {prop.description} - KeywordEnum");
                        sb.AppendLine($"{indent}    if (material.HasProperty(\"{prop.name}\"))");
                        sb.AppendLine($"{indent}    {{");
                        sb.AppendLine(
                            $"{indent}        int {GetPropertyVariableName(prop.name)}Value = (int)material.GetFloat(\"{prop.name}\");");

                        for (int i = 0; i < prop.keywordEnumKeywords.Length; i++)
                        {
                            string keyword = prop.keywordEnumKeywords[i];
                            sb.AppendLine(
                                $"{indent}        CoreUtils.SetKeyword(material, \"{keyword}\", {GetPropertyVariableName(prop.name)}Value == {i});");
                        }

                        sb.AppendLine($"{indent}    }}");
                    }
                }
            }
            else
            {
                sb.AppendLine($"{indent}    // 未找到需要设置的Shader关键字");
            }

            sb.AppendLine($"{indent}}}");
            sb.AppendLine();
        }

        private void GenerateShaderPropertiesGUIMethod(StringBuilder sb, List<ShaderPropertyInfo> properties, string indent)
        {
            sb.AppendLine($"{indent}public void ShaderPropertiesGUI(Material material)");
            sb.AppendLine($"{indent}{{");
            
            if (generateFoldouts && groupByPrefix)
            {
                var groups = GetPropertyGroups(properties);
                
                foreach (var group in groups)
                {
                    if (string.IsNullOrEmpty(group.Key))
                    {
                        foreach (var prop in group.Value)
                        {
                            GeneratePropertyGUI(sb, prop, indent + "    ");
                        }
                    }
                    else
                    {
                        string foldoutName = GetFoldoutVariableName(group.Key);
                        string displayName = FormatGroupName(group.Key);
                        
                        sb.AppendLine();
                        sb.AppendLine($"{indent}    {foldoutName} = EditorGUILayout.Foldout({foldoutName}, \"{displayName}\", true);");
                        sb.AppendLine($"{indent}    if ({foldoutName})");
                        sb.AppendLine($"{indent}    {{");
                        sb.AppendLine($"{indent}        EditorGUI.indentLevel++;");
                        
                        foreach (var prop in group.Value)
                        {
                            GeneratePropertyGUI(sb, prop, indent + "        ");
                        }
                        
                        sb.AppendLine($"{indent}        EditorGUI.indentLevel--;");
                        sb.AppendLine($"{indent}    }}");
                    }
                }
            }
            else
            {
                foreach (var prop in properties)
                {
                    GeneratePropertyGUI(sb, prop, indent + "    ");
                }
            }
            
            sb.AppendLine($"{indent}}}");
        }

        // 修改 GeneratePropertyGUI 方法，添加 KeywordEnum 的特殊处理
        private void GeneratePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string indent)
        {
            string varName = GetPropertyVariableName(prop.name);
            string styleName = GetStyleVariableName(prop.name);

            sb.AppendLine();
            sb.AppendLine($"{indent}// {prop.description}");
            sb.AppendLine($"{indent}if (properties.{varName} != null)");
            sb.AppendLine($"{indent}{{");

            switch (prop.type)
            {
                case ShaderUtil.ShaderPropertyType.TexEnv:
                    GenerateTexturePropertyGUI(sb, prop, varName, styleName, indent + "    ");
                    break;

                case ShaderUtil.ShaderPropertyType.Color:
                case ShaderUtil.ShaderPropertyType.Vector:
                    sb.AppendLine(
                        $"{indent}    materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
                    break;

                case ShaderUtil.ShaderPropertyType.Float:
                case ShaderUtil.ShaderPropertyType.Range:
                    // KeywordEnum 需要特殊处理
                    if (prop.isKeywordEnum && prop.keywordEnumKeywords != null && prop.keywordEnumKeywords.Length > 0)
                    {
                        GenerateKeywordEnumPropertyGUI(sb, prop, varName, styleName, indent + "    ");
                    }
                    else if (prop.isToggle && !string.IsNullOrEmpty(prop.keywordName))
                    {
                        GenerateTogglePropertyGUI(sb, prop, varName, styleName, indent + "    ");
                    }
                    else if (prop.isToggle)
                    {
                        GeneratePureTogglePropertyGUI(sb, prop, varName, styleName, indent + "    ");
                    }
                    else
                    {
                        sb.AppendLine(
                            $"{indent}    materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
                    }

                    break;
            }

            sb.AppendLine($"{indent}}}");
        }
        
        // 新增：生成 KeywordEnum 属性的 GUI 代码
        private void GenerateKeywordEnumPropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
        {
            sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
            sb.AppendLine($"{indent}materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
            sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
            sb.AppendLine($"{indent}{{");
            sb.AppendLine($"{indent}    MaterialChanged(material);");
            sb.AppendLine($"{indent}}}");
        }

        private void GenerateTexturePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
        {
            switch (textureStyle)
            {
                case TextureDisplayStyle.Default:
                    sb.AppendLine($"{indent}materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
                    break;
                    
                case TextureDisplayStyle.SingleLine:
                    sb.AppendLine($"{indent}materialEditor.TexturePropertySingleLine(Styles.{styleName}, properties.{varName});");
                    break;
                    
                case TextureDisplayStyle.LargeThumb:
                    sb.AppendLine($"{indent}materialEditor.TextureProperty(properties.{varName}, Styles.{styleName}.text);");
                    break;
            }
        }

        /// <summary>
        /// 生成纯 Toggle 属性的 GUI 代码（没有关联关键字）
        /// </summary>
        private void GeneratePureTogglePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName,
            string styleName, string indent)
        {
            // 纯 Toggle，不需要调用 MaterialChanged
            sb.AppendLine($"{indent}bool {varName}Enabled = properties.{varName}.floatValue >= 0.5f;");

            switch (toggleStyle)
            {
                case ToggleDisplayStyle.Toggle:
                    sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
                    sb.AppendLine(
                        $"{indent}{varName}Enabled = EditorGUILayout.Toggle(Styles.{styleName}, {varName}Enabled);");
                    sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
                    sb.AppendLine($"{indent}{{");
                    sb.AppendLine($"{indent}    properties.{varName}.floatValue = {varName}Enabled ? 1.0f : 0.0f;");
                    sb.AppendLine($"{indent}}}");
                    break;

                case ToggleDisplayStyle.ToggleLeft:
                    sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
                    sb.AppendLine(
                        $"{indent}{varName}Enabled = EditorGUILayout.ToggleLeft(Styles.{styleName}, {varName}Enabled);");
                    sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
                    sb.AppendLine($"{indent}{{");
                    sb.AppendLine($"{indent}    properties.{varName}.floatValue = {varName}Enabled ? 1.0f : 0.0f;");
                    sb.AppendLine($"{indent}}}");
                    break;

                case ToggleDisplayStyle.Foldout:
                    sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
                    sb.AppendLine(
                        $"{indent}{varName}Enabled = EditorGUILayout.Foldout({varName}Enabled, Styles.{styleName}, true);");
                    sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
                    sb.AppendLine($"{indent}{{");
                    sb.AppendLine($"{indent}    properties.{varName}.floatValue = {varName}Enabled ? 1.0f : 0.0f;");
                    sb.AppendLine($"{indent}}}");
                    break;

                case ToggleDisplayStyle.Button:
                    sb.AppendLine(
                        $"{indent}GUIStyle {varName}BtnStyle = {varName}Enabled ? new GUIStyle(EditorStyles.miniButton) {{ fontStyle = FontStyle.Bold }} : EditorStyles.miniButton;");
                    sb.AppendLine($"{indent}if (GUILayout.Button(Styles.{styleName}, {varName}BtnStyle))");
                    sb.AppendLine($"{indent}{{");
                    sb.AppendLine($"{indent}    properties.{varName}.floatValue = {varName}Enabled ? 0.0f : 1.0f;");
                    sb.AppendLine($"{indent}}}");
                    break;
            }
        }

        // 修改 GenerateTogglePropertyGUI 方法
        private void GenerateTogglePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
        {
            // 手动实现 Toggle，不依赖 Shader 中的 [Toggle] 属性
            sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
            sb.AppendLine($"{indent}bool {varName}Enabled = properties.{varName}.floatValue >= 0.5f;");
    
            switch (toggleStyle)
            {
                case ToggleDisplayStyle.Toggle:
                    sb.AppendLine($"{indent}{varName}Enabled = EditorGUILayout.Toggle(Styles.{styleName}, {varName}Enabled);");
                    break;
            
                case ToggleDisplayStyle.ToggleLeft:
                    sb.AppendLine($"{indent}{varName}Enabled = EditorGUILayout.ToggleLeft(Styles.{styleName}, {varName}Enabled);");
                    break;
            
                case ToggleDisplayStyle.Foldout:
                    sb.AppendLine($"{indent}{varName}Enabled = EditorGUILayout.Foldout({varName}Enabled, Styles.{styleName}, true);");
                    break;
            
                case ToggleDisplayStyle.Button:
                    sb.AppendLine($"{indent}var {varName}Style = {varName}Enabled ? EditorStyles.toolbarButton : EditorStyles.miniButton;");
                    sb.AppendLine($"{indent}if (GUILayout.Button(Styles.{styleName}, {varName}Style))");
                    sb.AppendLine($"{indent}    {varName}Enabled = !{varName}Enabled;");
                    break;
            }
    
            sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
            sb.AppendLine($"{indent}{{");
            sb.AppendLine($"{indent}    properties.{varName}.floatValue = {varName}Enabled ? 1.0f : 0.0f;");
            sb.AppendLine($"{indent}    MaterialChanged(material);");
            sb.AppendLine($"{indent}}}");
        }
        //--------------因为增加手动实现Toggle属性，所以需要修改GenerateTogglePropertyGUI方法------------
        // private void GenerateTogglePropertyGUI(StringBuilder sb, ShaderPropertyInfo prop, string varName, string styleName, string indent)
        // {
        //     sb.AppendLine($"{indent}EditorGUI.BeginChangeCheck();");
        //     sb.AppendLine($"{indent}materialEditor.ShaderProperty(properties.{varName}, Styles.{styleName});");
        //     sb.AppendLine($"{indent}if (EditorGUI.EndChangeCheck())");
        //     sb.AppendLine($"{indent}{{");
        //     sb.AppendLine($"{indent}    MaterialChanged(material);");
        //     sb.AppendLine($"{indent}}}");
        // }

        private Dictionary<string, List<ShaderPropertyInfo>> GetPropertyGroups(List<ShaderPropertyInfo> properties)
        {
            var groups = new Dictionary<string, List<ShaderPropertyInfo>>();
            
            if (!groupByPrefix)
            {
                groups[""] = properties;
                return groups;
            }
            
            var groupPrefixes = new Dictionary<string, string>
            {
                { "base", "基础设置" },
                { "main", "主贴图" },
                { "tint", "颜色" },
                { "color", "颜色" },
                { "metallic", "金属/粗糙度" },
                { "normal", "法线" },
                { "bump", "法线" },
                { "emission", "自发光" },
                { "rim", "边缘光" },
                { "sss", "次表面散射" },
                { "uvlight", "UV流光" },
                { "cube", "环境贴图" },
                { "effect", "特效" },
                { "light", "光照" },
                { "specular", "高光" },
                { "aniso", "各向异性" },
                { "rain", "雨滴效果" },
                { "camera", "相机" },
                { "reflect", "反射" },
                { "occlusion", "AO" },
                { "ao", "AO" },
                { "diss", "溶解" },
                { "dissolve", "溶解" },
                { "mask", "遮罩" },
                { "custom", "自定义数据" },
                { "uv", "UV" },
                { "alpha", "透明度" },
                { "cull", "渲染状态" },
                { "stencil", "渲染状态" },
                { "zwrite", "渲染状态" },
                { "ztest", "渲染状态" },
                { "blend", "渲染状态" },
                { "dst", "渲染状态" },
                { "noise", "噪波" },
                { "niqu", "扭曲" },
                { "distort", "扭曲" },
                { "nq", "扭曲" },
                { "vertex", "顶点" },
                { "fresnel", "菲涅尔" },
                { "soft", "软粒子" },
                { "fov", "透视" },
                { "ui", "UI" },
                { "additional", "附加光" },
            };
            
            foreach (var prop in properties)
            {
                string propLower = prop.name.TrimStart('_').ToLower();
                string groupKey = "";
                
                foreach (var prefix in groupPrefixes)
                {
                    if (propLower.StartsWith(prefix.Key))
                    {
                        groupKey = prefix.Value;
                        break;
                    }
                }
                
                if (!groups.ContainsKey(groupKey))
                {
                    groups[groupKey] = new List<ShaderPropertyInfo>();
                }
                
                groups[groupKey].Add(prop);
            }
            
            return groups;
        }

        private string GetStyleVariableName(string propertyName)
        {
            string name = propertyName.TrimStart('_');
            if (name.Length > 0)
            {
                name = char.ToLower(name[0]) + name.Substring(1);
            }
            return name + "Text";
        }

        private string GetPropertyVariableName(string propertyName)
        {
            string name = propertyName.TrimStart('_');
            if (name.Length > 0)
            {
                name = char.ToLower(name[0]) + name.Substring(1);
            }
            return name;
        }

        private string GetFoldoutVariableName(string groupName)
        {
            string name = groupName.Replace(" ", "").Replace("/", "");
            return "show" + name + "Foldout";
        }

        private string FormatGroupName(string groupKey)
        {
            return groupKey;
        }

        // 修改 GenerateTooltip 方法，为 KeywordEnum 添加更详细的提示
        private string GenerateTooltip(ShaderPropertyInfo prop)
        {
            var parts = new List<string>();
    
            if (prop.type == ShaderUtil.ShaderPropertyType.Range)
            {
                parts.Add($"范围: {prop.rangeMin} - {prop.rangeMax}");
            }
    
            if (!string.IsNullOrEmpty(prop.keywordName))
            {
                parts.Add($"关键字: {prop.keywordName}");
            }
    
            // KeywordEnum 的关键字列表
            if (prop.isKeywordEnum && prop.keywordEnumKeywords != null && prop.keywordEnumKeywords.Length > 0)
            {
                parts.Add($"关键字: {string.Join(", ", prop.keywordEnumKeywords)}");
            }
    
            if (!string.IsNullOrEmpty(prop.attributeType))
            {
                parts.Add($"类型: {prop.attributeType}");
            }
    
            return string.Join(" | ", parts);
        }

        private string EscapeString(string str)
        {
            if (string.IsNullOrEmpty(str)) return "";
            return str.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private void SaveGeneratedCode()
        {
            if (string.IsNullOrEmpty(generatedCode))
            {
                EditorUtility.DisplayDialog("错误", "没有可保存的代码", "确定");
                return;
            }
            
            string fileName = outputClassName + ".cs";
            string fullPath = Path.Combine(outputPath, fileName);
            
            string directory = Path.GetDirectoryName(fullPath);
            if (!Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }
            
            if (File.Exists(fullPath))
            {
                if (!EditorUtility.DisplayDialog("文件已存在", 
                    $"文件 {fileName} 已存在，是否覆盖？", "覆盖", "取消"))
                {
                    return;
                }
            }
            
            File.WriteAllText(fullPath, generatedCode, Encoding.UTF8);
            AssetDatabase.Refresh();
            
            EditorUtility.DisplayDialog("成功", $"文件已保存到:\n{fullPath}", "确定");
            
            var asset = AssetDatabase.LoadAssetAtPath<MonoScript>(fullPath);
            if (asset != null)
            {
                Selection.activeObject = asset;
                EditorGUIUtility.PingObject(asset);
            }
        }
    }
}