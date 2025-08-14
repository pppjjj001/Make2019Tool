// using System.Collections.Generic;
// using System.Linq;
// using UnityEngine;
// using UnityEditor;
//
// public class MaterialKeywordChecker : EditorWindow
// {
//     [System.Serializable]
//     public class PropertyKeywordRule
//     {
//         public string propertyName = "";
//         public float propertyValue = 1.0f;
//         public string[] requiredKeywords = new string[0];
//         public bool foldout = true;
//     }
//
//     private List<PropertyKeywordRule> rules = new List<PropertyKeywordRule>();
//     private List<Material> unmatchedMaterials = new List<Material>();
//     private Vector2 scrollPosition;
//     private Vector2 resultScrollPosition;
//     private bool showResults = false;
//
//     [MenuItem("Tools/TempByAI/Material Keyword Checker")]
//     public static void ShowWindow()
//     {
//         GetWindow<MaterialKeywordChecker>("Material Keyword Checker");
//     }
//
//     private void OnEnable()
//     {
//         if (rules.Count == 0)
//         {
//             rules.Add(new PropertyKeywordRule());
//         }
//     }
//
//     private void OnGUI()
//     {
//         GUILayout.Label("Material Keyword Checker", EditorStyles.boldLabel);
//         GUILayout.Space(10);
//
//         scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);
//
//         // 显示规则设置
//         GUILayout.Label("Property-Keyword Rules", EditorStyles.boldLabel);
//         
//         for (int i = 0; i < rules.Count; i++)
//         {
//             DrawRule(i);
//         }
//
//         GUILayout.Space(10);
//         
//         // 添加和删除规则按钮
//         GUILayout.BeginHorizontal();
//         if (GUILayout.Button("Add Rule"))
//         {
//             rules.Add(new PropertyKeywordRule());
//         }
//         
//         if (GUILayout.Button("Remove Last Rule") && rules.Count > 0)
//         {
//             rules.RemoveAt(rules.Count - 1);
//         }
//         GUILayout.EndHorizontal();
//
//         GUILayout.Space(20);
//
//         // 扫描按钮
//         if (GUILayout.Button("Scan All Materials", GUILayout.Height(30)))
//         {
//             ScanMaterials();
//         }
//
//         GUILayout.Space(10);
//
//         // 显示结果
//         if (showResults)
//         {
//             DrawResults();
//         }
//
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void DrawRule(int index)
//     {
//         var rule = rules[index];
//         
//         GUILayout.BeginVertical(EditorStyles.helpBox);
//         
//         rule.foldout = EditorGUILayout.Foldout(rule.foldout, $"Rule {index + 1}");
//         
//         if (rule.foldout)
//         {
//             EditorGUI.indentLevel++;
//             
//             // 属性名称
//             rule.propertyName = EditorGUILayout.TextField("Property Name", rule.propertyName);
//             
//             // 属性值
//             rule.propertyValue = EditorGUILayout.FloatField("Property Value", rule.propertyValue);
//             
//             // 关键字数组
//             GUILayout.Label("Required Keywords:");
//             
//             // 显示现有关键字
//             for (int i = 0; i < rule.requiredKeywords.Length; i++)
//             {
//                 GUILayout.BeginHorizontal();
//                 rule.requiredKeywords[i] = EditorGUILayout.TextField($"Keyword {i + 1}", rule.requiredKeywords[i]);
//                 if (GUILayout.Button("X", GUILayout.Width(20)))
//                 {
//                     RemoveKeywordAt(rule, i);
//                 }
//                 GUILayout.EndHorizontal();
//             }
//             
//             // 添加关键字按钮
//             if (GUILayout.Button("Add Keyword"))
//             {
//                 AddKeywordToRule(rule);
//             }
//             
//             EditorGUI.indentLevel--;
//         }
//         
//         GUILayout.EndVertical();
//         GUILayout.Space(5);
//     }
//
//     private void AddKeywordToRule(PropertyKeywordRule rule)
//     {
//         var newKeywords = new string[rule.requiredKeywords.Length + 1];
//         rule.requiredKeywords.CopyTo(newKeywords, 0);
//         newKeywords[newKeywords.Length - 1] = "";
//         rule.requiredKeywords = newKeywords;
//     }
//
//     private void RemoveKeywordAt(PropertyKeywordRule rule, int index)
//     {
//         var newKeywords = new string[rule.requiredKeywords.Length - 1];
//         for (int i = 0, j = 0; i < rule.requiredKeywords.Length; i++)
//         {
//             if (i != index)
//             {
//                 newKeywords[j++] = rule.requiredKeywords[i];
//             }
//         }
//         rule.requiredKeywords = newKeywords;
//     }
//
//     private void ScanMaterials()
//     {
//         unmatchedMaterials.Clear();
//         
//         // 获取项目中所有材质
//         string[] materialGUIDs = AssetDatabase.FindAssets("t:Material");
//         
//         foreach (string guid in materialGUIDs)
//         {
//             string path = AssetDatabase.GUIDToAssetPath(guid);
//             Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
//             
//             if (material == null) continue;
//             
//             // 检查材质是否违反任何规则
//             if (IsMaterialUnmatched(material))
//             {
//                 unmatchedMaterials.Add(material);
//             }
//         }
//         
//         showResults = true;
//         Debug.Log($"扫描完成！找到 {unmatchedMaterials.Count} 个不匹配的材质");
//     }
//
//     private bool IsMaterialUnmatched(Material material)
//     {
//         foreach (var rule in rules)
//         {
//             if (string.IsNullOrEmpty(rule.propertyName)) continue;
//             
//             // 检查材质是否有这个属性
//             if (!material.HasProperty(rule.propertyName)) continue;
//             
//             // 检查属性值是否匹配
//             float materialValue = 0f;
//             
//             // 根据属性类型获取值
//             var shader = material.shader;
//             int propertyIndex = -1;
//             
//             for (int i = 0; i < ShaderUtil.GetPropertyCount(shader); i++)
//             {
//                 if (ShaderUtil.GetPropertyName(shader, i) == rule.propertyName)
//                 {
//                     propertyIndex = i;
//                     break;
//                 }
//             }
//             
//             if (propertyIndex == -1) continue;
//             
//             var propertyType = ShaderUtil.GetPropertyType(shader, propertyIndex);
//             
//             switch (propertyType)
//             {
//                 case ShaderUtil.ShaderPropertyType.Float:
//                 case ShaderUtil.ShaderPropertyType.Range:
//                     materialValue = material.GetFloat(rule.propertyName);
//                     break;
//                 case ShaderUtil.ShaderPropertyType.Color:
//                     // 对于颜色，可能需要检查alpha值或其他分量
//                     Color color = material.GetColor(rule.propertyName);
//                     materialValue = color.a; // 默认检查alpha值
//                     break;
//                 case ShaderUtil.ShaderPropertyType.Vector:
//                     Vector4 vector = material.GetVector(rule.propertyName);
//                     materialValue = vector.x; // 默认检查x分量
//                     break;
//                 default:
//                     continue;
//             }
//             
//             // 如果属性值匹配规则值
//             if (Mathf.Approximately(materialValue, rule.propertyValue))
//             {
//                 // 检查是否有对应的关键字
//                 bool hasAllKeywords = true;
//                 
//                 foreach (string keyword in rule.requiredKeywords)
//                 {
//                     if (string.IsNullOrEmpty(keyword)) continue;
//                     
//                     if (!material.IsKeywordEnabled(keyword))
//                     {
//                         hasAllKeywords = false;
//                         break;
//                     }
//                 }
//                 
//                 // 如果属性值匹配但缺少必需的关键字，则添加到不匹配列表
//                 if (!hasAllKeywords)
//                 {
//                     return true;
//                 }
//             }
//         }
//         
//         return false;
//     }
//
//     private void DrawResults()
//     {
//         GUILayout.Label($"Unmatched Materials ({unmatchedMaterials.Count})", EditorStyles.boldLabel);
//         
//         if (unmatchedMaterials.Count == 0)
//         {
//             EditorGUILayout.HelpBox("所有材质都正确匹配了属性和关键字！", MessageType.Info);
//             return;
//         }
//         
//         resultScrollPosition = EditorGUILayout.BeginScrollView(resultScrollPosition, GUILayout.Height(300));
//         
//         foreach (var material in unmatchedMaterials)
//         {
//             GUILayout.BeginHorizontal(EditorStyles.helpBox);
//             
//             // 材质图标和名称
//             EditorGUILayout.ObjectField(material, typeof(Material), false);
//             
//             // 显示详细信息按钮
//             if (GUILayout.Button("Details", GUILayout.Width(60)))
//             {
//                 ShowMaterialDetails(material);
//             }
//             
//             // 选择按钮
//             if (GUILayout.Button("Select", GUILayout.Width(50)))
//             {
//                 Selection.activeObject = material;
//                 EditorGUIUtility.PingObject(material);
//             }
//             
//             GUILayout.EndHorizontal();
//         }
//         
//         EditorGUILayout.EndScrollView();
//         
//         GUILayout.Space(10);
//         
//         // 批量操作按钮
//         GUILayout.BeginHorizontal();
//         if (GUILayout.Button("Fix All Materials"))
//         {
//             FixAllMaterials();
//         }
//         
//         if (GUILayout.Button("Select All Unmatched"))
//         {
//             Selection.objects = unmatchedMaterials.ToArray();
//         }
//         GUILayout.EndHorizontal();
//     }
//
//     private void ShowMaterialDetails(Material material)
//     {
//         string details = $"Material: {material.name}\n";
//         details += $"Shader: {material.shader.name}\n\n";
//         
//         details += "Current Keywords:\n";
//         foreach (string keyword in material.shaderKeywords)
//         {
//             details += $"- {keyword}\n";
//         }
//         
//         details += "\nViolated Rules:\n";
//         
//         foreach (var rule in rules)
//         {
//             if (string.IsNullOrEmpty(rule.propertyName)) continue;
//             
//             if (material.HasProperty(rule.propertyName))
//             {
//                 float value = material.GetFloat(rule.propertyName);
//                 if (Mathf.Approximately(value, rule.propertyValue))
//                 {
//                     details += $"Property '{rule.propertyName}' = {value}, missing keywords: ";
//                     foreach (string keyword in rule.requiredKeywords)
//                     {
//                         if (!string.IsNullOrEmpty(keyword) && !material.IsKeywordEnabled(keyword))
//                         {
//                             details += $"{keyword} ";
//                         }
//                     }
//                     details += "\n";
//                 }
//             }
//         }
//         
//         EditorUtility.DisplayDialog("Material Details", details, "OK");
//     }
//
//     private void FixAllMaterials()
//     {
//         if (EditorUtility.DisplayDialog("Fix Materials", 
//             $"是否要自动修复 {unmatchedMaterials.Count} 个材质的关键字？", "Yes", "No"))
//         {
//             int fixedCount = 0;
//             
//             foreach (var material in unmatchedMaterials)
//             {
//                 if (FixMaterial(material))
//                 {
//                     fixedCount++;
//                 }
//             }
//             
//             AssetDatabase.SaveAssets();
//             Debug.Log($"已修复 {fixedCount} 个材质");
//             
//             // 重新扫描
//             ScanMaterials();
//         }
//     }
//
//     private bool FixMaterial(Material material)
//     {
//         bool wasFixed = false;
//         
//         foreach (var rule in rules)
//         {
//             if (string.IsNullOrEmpty(rule.propertyName)) continue;
//             
//             if (material.HasProperty(rule.propertyName))
//             {
//                 float value = material.GetFloat(rule.propertyName);
//                 if (Mathf.Approximately(value, rule.propertyValue))
//                 {
//                     foreach (string keyword in rule.requiredKeywords)
//                     {
//                         if (!string.IsNullOrEmpty(keyword) && !material.IsKeywordEnabled(keyword))
//                         {
//                             material.EnableKeyword(keyword);
//                             wasFixed = true;
//                         }
//                     }
//                 }
//             }
//         }
//         
//         if (wasFixed)
//         {
//             EditorUtility.SetDirty(material);
//         }
//         
//         return wasFixed;
//     }
// }
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEditor;

public class MaterialKeywordChecker : EditorWindow
{
    public enum PropertyTypeFilter
    {
        Auto,           // 自动检测（原逻辑）
        FloatOrRange,   // Float和Range类型
        Color,          // Color类型
        Vector          // Vector类型
    }

    public enum ColorComponent
    {
        R, G, B, A
    }

    public enum VectorComponent
    {
        X, Y, Z, W
    }

    [System.Serializable]
    public class PropertyKeywordRule
    {
        public string shaderName = "";
        public string propertyName = "";
        public PropertyTypeFilter propertyTypeFilter = PropertyTypeFilter.Auto;
        
        // 不同类型的值
        public float floatValue = 1.0f;
        public Color colorValue = Color.white;
        public ColorComponent colorComponent = ColorComponent.A;
        public Vector4 vectorValue = Vector4.zero;
        public VectorComponent vectorComponent = VectorComponent.X;
        
        public string[] requiredKeywords = new string[0];
        public bool foldout = true;
    }

    private List<PropertyKeywordRule> rules = new List<PropertyKeywordRule>();
    private List<Material> unmatchedMaterials = new List<Material>();
    private Vector2 scrollPosition;
    private Vector2 resultScrollPosition;
    private bool showResults = false;

    [MenuItem("Tools/TempByAI/Material Keyword Checker")]
    public static void ShowWindow()
    {
        GetWindow<MaterialKeywordChecker>("Material Keyword Checker");
    }

    private void OnEnable()
    {
        if (rules.Count == 0)
        {
            rules.Add(new PropertyKeywordRule());
        }
    }

    private void OnGUI()
    {
        GUILayout.Label("Material Keyword Checker", EditorStyles.boldLabel);
        GUILayout.Space(10);

        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

        // 显示规则设置
        GUILayout.Label("Property-Keyword Rules", EditorStyles.boldLabel);
        
        for (int i = 0; i < rules.Count; i++)
        {
            DrawRule(i);
        }

        GUILayout.Space(10);
        
        // 添加和删除规则按钮
        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Add Rule"))
        {
            rules.Add(new PropertyKeywordRule());
        }
        
        if (GUILayout.Button("Remove Last Rule") && rules.Count > 0)
        {
            rules.RemoveAt(rules.Count - 1);
        }
        GUILayout.EndHorizontal();

        GUILayout.Space(20);

        // 扫描按钮
        if (GUILayout.Button("Scan All Materials", GUILayout.Height(30)))
        {
            ScanMaterials();
        }

        GUILayout.Space(10);

        // 显示结果
        if (showResults)
        {
            DrawResults();
        }

        EditorGUILayout.EndScrollView();
    }

    private void DrawRule(int index)
    {
        var rule = rules[index];
        
        GUILayout.BeginVertical(EditorStyles.helpBox);
        
        rule.foldout = EditorGUILayout.Foldout(rule.foldout, $"Rule {index + 1}");
        
        if (rule.foldout)
        {
            EditorGUI.indentLevel++;
            
            // Shader名称过滤
            EditorGUILayout.LabelField("Shader Filter (留空则匹配所有Shader):", EditorStyles.miniBoldLabel);
            rule.shaderName = EditorGUILayout.TextField("Shader Name", rule.shaderName);
            
            // 显示提示信息
            if (!string.IsNullOrEmpty(rule.shaderName))
            {
                EditorGUILayout.HelpBox($"只检查使用 '{rule.shaderName}' Shader的材质", MessageType.Info);
            }
            else
            {
                EditorGUILayout.HelpBox("将检查所有Shader的材质", MessageType.Info);
            }
            
            GUILayout.Space(5);
            
            // 属性名称
            rule.propertyName = EditorGUILayout.TextField("Property Name", rule.propertyName);
            
            // 属性类型过滤
            rule.propertyTypeFilter = (PropertyTypeFilter)EditorGUILayout.EnumPopup("Property Type", rule.propertyTypeFilter);
            
            // 根据属性类型显示对应的值输入
            DrawPropertyValue(rule);
            
            GUILayout.Space(5);
            
            // 关键字数组
            GUILayout.Label("Required Keywords:");
            
            // 显示现有关键字
            for (int i = 0; i < rule.requiredKeywords.Length; i++)
            {
                GUILayout.BeginHorizontal();
                rule.requiredKeywords[i] = EditorGUILayout.TextField($"Keyword {i + 1}", rule.requiredKeywords[i]);
                if (GUILayout.Button("X", GUILayout.Width(20)))
                {
                    RemoveKeywordAt(rule, i);
                }
                GUILayout.EndHorizontal();
            }
            
            // 添加关键字按钮
            if (GUILayout.Button("Add Keyword"))
            {
                AddKeywordToRule(rule);
            }
            
            EditorGUI.indentLevel--;
        }
        
        GUILayout.EndVertical();
        GUILayout.Space(5);
    }

    private void DrawPropertyValue(PropertyKeywordRule rule)
    {
        switch (rule.propertyTypeFilter)
        {
            case PropertyTypeFilter.Auto:
                rule.floatValue = EditorGUILayout.FloatField("Property Value", rule.floatValue);
                EditorGUILayout.HelpBox("自动检测属性类型并使用对应的默认比较值", MessageType.Info);
                break;
                
            case PropertyTypeFilter.FloatOrRange:
                rule.floatValue = EditorGUILayout.FloatField("Float Value", rule.floatValue);
                break;
                
            case PropertyTypeFilter.Color:
                rule.colorValue = EditorGUILayout.ColorField("Color Value", rule.colorValue);
                rule.colorComponent = (ColorComponent)EditorGUILayout.EnumPopup("Compare Component", rule.colorComponent);
                EditorGUILayout.HelpBox($"将比较颜色的 {rule.colorComponent} 分量", MessageType.Info);
                break;
                
            case PropertyTypeFilter.Vector:
                rule.vectorValue = EditorGUILayout.Vector4Field("Vector Value", rule.vectorValue);
                rule.vectorComponent = (VectorComponent)EditorGUILayout.EnumPopup("Compare Component", rule.vectorComponent);
                EditorGUILayout.HelpBox($"将比较向量的 {rule.vectorComponent} 分量", MessageType.Info);
                break;
        }
    }

    private void AddKeywordToRule(PropertyKeywordRule rule)
    {
        var newKeywords = new string[rule.requiredKeywords.Length + 1];
        rule.requiredKeywords.CopyTo(newKeywords, 0);
        newKeywords[newKeywords.Length - 1] = "";
        rule.requiredKeywords = newKeywords;
    }

    private void RemoveKeywordAt(PropertyKeywordRule rule, int index)
    {
        var newKeywords = new string[rule.requiredKeywords.Length - 1];
        for (int i = 0, j = 0; i < rule.requiredKeywords.Length; i++)
        {
            if (i != index)
            {
                newKeywords[j++] = rule.requiredKeywords[i];
            }
        }
        rule.requiredKeywords = newKeywords;
    }

    private void ScanMaterials()
    {
        unmatchedMaterials.Clear();
        
        // 获取项目中所有材质
        string[] materialGUIDs = AssetDatabase.FindAssets("t:Material");
        
        foreach (string guid in materialGUIDs)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            
            if (material == null) continue;
            
            // 检查材质是否违反任何规则
            if (IsMaterialUnmatched(material))
            {
                unmatchedMaterials.Add(material);
            }
        }
        
        showResults = true;
        Debug.Log($"扫描完成！找到 {unmatchedMaterials.Count} 个不匹配的材质");
    }

    private bool IsMaterialUnmatched(Material material)
    {
        foreach (var rule in rules)
        {
            // 如果规则指定了shader名称，先检查shader是否匹配
            if (!string.IsNullOrEmpty(rule.shaderName))
            {
                if (material.shader.name != rule.shaderName)
                {
                    continue; // Shader不匹配，跳过此规则
                }
            }
            
            if (string.IsNullOrEmpty(rule.propertyName)) continue;
            
            // 检查材质是否有这个属性
            if (!material.HasProperty(rule.propertyName)) continue;
            
            // 获取材质属性值并与规则比较
            float materialValue = GetMaterialPropertyValue(material, rule);
            float ruleValue = GetRuleCompareValue(rule, material);
            
            if (float.IsNaN(materialValue)) continue; // 无法获取有效值
            
            // 如果属性值匹配规则值
            if (Mathf.Approximately(materialValue, ruleValue))
            {
                // 检查是否有对应的关键字
                bool hasAllKeywords = true;
                
                foreach (string keyword in rule.requiredKeywords)
                {
                    if (string.IsNullOrEmpty(keyword)) continue;
                    
                    if (!material.IsKeywordEnabled(keyword))
                    {
                        hasAllKeywords = false;
                        break;
                    }
                }
                
                // 如果属性值匹配但缺少必需的关键字，则添加到不匹配列表
                if (!hasAllKeywords)
                {
                    return true;
                }
            }
        }
        
        return false;
    }

    private float GetMaterialPropertyValue(Material material, PropertyKeywordRule rule)
    {
        var shader = material.shader;
        int propertyIndex = -1;
        
        // 找到属性索引
        for (int i = 0; i < ShaderUtil.GetPropertyCount(shader); i++)
        {
            if (ShaderUtil.GetPropertyName(shader, i) == rule.propertyName)
            {
                propertyIndex = i;
                break;
            }
        }
        
        if (propertyIndex == -1) return float.NaN;
        
        var propertyType = ShaderUtil.GetPropertyType(shader, propertyIndex);
        
        // 如果指定了属性类型，检查是否匹配
        if (rule.propertyTypeFilter != PropertyTypeFilter.Auto)
        {
            if (!IsPropertyTypeMatched(propertyType, rule.propertyTypeFilter))
            {
                return float.NaN; // 类型不匹配
            }
        }
        
        // 根据指定的类型或自动检测的类型获取值
        switch (rule.propertyTypeFilter)
        {
            case PropertyTypeFilter.FloatOrRange:
                return material.GetFloat(rule.propertyName);
                
            case PropertyTypeFilter.Color:
                Color color = material.GetColor(rule.propertyName);
                return GetColorComponent(color, rule.colorComponent);
                
            case PropertyTypeFilter.Vector:
                Vector4 vector = material.GetVector(rule.propertyName);
                return GetVectorComponent(vector, rule.vectorComponent);
                
            case PropertyTypeFilter.Auto:
            default:
                // 原逻辑：根据实际属性类型自动处理
                switch (propertyType)
                {
                    case ShaderUtil.ShaderPropertyType.Float:
                    case ShaderUtil.ShaderPropertyType.Range:
                        return material.GetFloat(rule.propertyName);
                    case ShaderUtil.ShaderPropertyType.Color:
                        Color autoColor = material.GetColor(rule.propertyName);
                        return autoColor.a; // 默认检查alpha值
                    case ShaderUtil.ShaderPropertyType.Vector:
                        Vector4 autoVector = material.GetVector(rule.propertyName);
                        return autoVector.x; // 默认检查x分量
                    default:
                        return float.NaN;
                }
        }
    }

    private float GetRuleCompareValue(PropertyKeywordRule rule, Material material)
    {
        switch (rule.propertyTypeFilter)
        {
            case PropertyTypeFilter.FloatOrRange:
                return rule.floatValue;
                
            case PropertyTypeFilter.Color:
                return GetColorComponent(rule.colorValue, rule.colorComponent);
                
            case PropertyTypeFilter.Vector:
                return GetVectorComponent(rule.vectorValue, rule.vectorComponent);
                
            case PropertyTypeFilter.Auto:
            default:
                return rule.floatValue;
        }
    }

    private bool IsPropertyTypeMatched(ShaderUtil.ShaderPropertyType actualType, PropertyTypeFilter filterType)
    {
        switch (filterType)
        {
            case PropertyTypeFilter.FloatOrRange:
                return actualType == ShaderUtil.ShaderPropertyType.Float || 
                       actualType == ShaderUtil.ShaderPropertyType.Range;
                       
            case PropertyTypeFilter.Color:
                return actualType == ShaderUtil.ShaderPropertyType.Color;
                
            case PropertyTypeFilter.Vector:
                return actualType == ShaderUtil.ShaderPropertyType.Vector;
                
            default:
                return true;
        }
    }

    private float GetColorComponent(Color color, ColorComponent component)
    {
        switch (component)
        {
            case ColorComponent.R: return color.r;
            case ColorComponent.G: return color.g;
            case ColorComponent.B: return color.b;
            case ColorComponent.A: return color.a;
            default: return color.a;
        }
    }

    private float GetVectorComponent(Vector4 vector, VectorComponent component)
    {
        switch (component)
        {
            case VectorComponent.X: return vector.x;
            case VectorComponent.Y: return vector.y;
            case VectorComponent.Z: return vector.z;
            case VectorComponent.W: return vector.w;
            default: return vector.x;
        }
    }

    private void DrawResults()
    {
        GUILayout.Label($"Unmatched Materials ({unmatchedMaterials.Count})", EditorStyles.boldLabel);
        
        if (unmatchedMaterials.Count == 0)
        {
            EditorGUILayout.HelpBox("所有材质都正确匹配了属性和关键字！", MessageType.Info);
            return;
        }
        
        resultScrollPosition = EditorGUILayout.BeginScrollView(resultScrollPosition, GUILayout.Height(300));
        
        foreach (var material in unmatchedMaterials)
        {
            GUILayout.BeginHorizontal(EditorStyles.helpBox);
            
            // 材质图标和名称
            EditorGUILayout.ObjectField(material, typeof(Material), false);
            
            // 显示Shader名称
            EditorGUILayout.LabelField(material.shader.name, GUILayout.Width(150));
            
            // 显示详细信息按钮
            if (GUILayout.Button("Details", GUILayout.Width(60)))
            {
                ShowMaterialDetails(material);
            }
            
            // 选择按钮
            if (GUILayout.Button("Select", GUILayout.Width(50)))
            {
                Selection.activeObject = material;
                EditorGUIUtility.PingObject(material);
            }
            
            GUILayout.EndHorizontal();
        }
        
        EditorGUILayout.EndScrollView();
        
        GUILayout.Space(10);
        
        // 批量操作按钮
        GUILayout.BeginHorizontal();
        if (GUILayout.Button("Fix All Materials"))
        {
            FixAllMaterials();
        }
        
        if (GUILayout.Button("Select All Unmatched"))
        {
            Selection.objects = unmatchedMaterials.ToArray();
        }
        GUILayout.EndHorizontal();
    }

    private void ShowMaterialDetails(Material material)
    {
        string details = $"Material: {material.name}\n";
        details += $"Shader: {material.shader.name}\n\n";
        
        details += "Current Keywords:\n";
        foreach (string keyword in material.shaderKeywords)
        {
            details += $"- {keyword}\n";
        }
        
        details += "\nViolated Rules:\n";
        
        foreach (var rule in rules)
        {
            // 检查Shader名称匹配
            if (!string.IsNullOrEmpty(rule.shaderName) && material.shader.name != rule.shaderName)
            {
                continue;
            }
            
            if (string.IsNullOrEmpty(rule.propertyName)) continue;
            
            if (material.HasProperty(rule.propertyName))
            {
                float materialValue = GetMaterialPropertyValue(material, rule);
                float ruleValue = GetRuleCompareValue(rule, material);
                
                if (!float.IsNaN(materialValue) && Mathf.Approximately(materialValue, ruleValue))
                {
                    details += $"Rule: Shader='{rule.shaderName}', Property '{rule.propertyName}' ";
                    details += $"(Type: {rule.propertyTypeFilter}) = {materialValue}, missing keywords: ";
                    
                    foreach (string keyword in rule.requiredKeywords)
                    {
                        if (!string.IsNullOrEmpty(keyword) && !material.IsKeywordEnabled(keyword))
                        {
                            details += $"{keyword} ";
                        }
                    }
                    details += "\n";
                }
            }
        }
        
        EditorUtility.DisplayDialog("Material Details", details, "OK");
    }

    private void FixAllMaterials()
    {
        if (EditorUtility.DisplayDialog("Fix Materials", 
            $"是否要自动修复 {unmatchedMaterials.Count} 个材质的关键字？", "Yes", "No"))
        {
            int fixedCount = 0;
            
            foreach (var material in unmatchedMaterials)
            {
                if (FixMaterial(material))
                {
                    fixedCount++;
                }
            }
            
            AssetDatabase.SaveAssets();
            Debug.Log($"已修复 {fixedCount} 个材质");
            
            // 重新扫描
            ScanMaterials();
        }
    }

    private bool FixMaterial(Material material)
    {
        bool wasFixed = false;
        
        foreach (var rule in rules)
        {
            // 检查Shader名称匹配
            if (!string.IsNullOrEmpty(rule.shaderName) && material.shader.name != rule.shaderName)
            {
                continue;
            }
            
            if (string.IsNullOrEmpty(rule.propertyName)) continue;
            
            if (material.HasProperty(rule.propertyName))
            {
                float materialValue = GetMaterialPropertyValue(material, rule);
                float ruleValue = GetRuleCompareValue(rule, material);
                
                if (!float.IsNaN(materialValue) && Mathf.Approximately(materialValue, ruleValue))
                {
                    foreach (string keyword in rule.requiredKeywords)
                    {
                        if (!string.IsNullOrEmpty(keyword) && !material.IsKeywordEnabled(keyword))
                        {
                            material.EnableKeyword(keyword);
                            wasFixed = true;
                        }
                    }
                }
            }
        }
        
        if (wasFixed)
        {
            EditorUtility.SetDirty(material);
        }
        
        return wasFixed;
    }
}
