using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class MaterialParameterSetter : EditorWindow
{
    private Material targetMaterial;
    private string parameterData = "";
    private Vector2 scrollPos;
    private Vector2 previewScrollPos;
    private bool showPreview = false;
    private List<ParameterInfo> parsedParameters = new List<ParameterInfo>();
    private string csvFilePath = "";
    private int importMode = 0; // 0: 手动输入, 1: CSV文件
    
    // CSV 导入设置
    private bool hasHeader = true;
    private char delimiter = ',';
    private string customDelimiter = ",";
    
    [System.Serializable]
    public class ParameterInfo
    {
        public string name;
        public string value;
        public string type;
        public bool willApply;
        public string matchedPropertyName;
    }

    [MenuItem("Tools/TempByAI/Material Parameter Setter")]
    public static void ShowWindow()
    {
        GetWindow<MaterialParameterSetter>("材质参数设置工具");
    }

    private void OnGUI()
    {
        GUILayout.Label("材质参数批量设置工具", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // 选择目标材质
        targetMaterial = (Material)EditorGUILayout.ObjectField("目标材质", targetMaterial, typeof(Material), false);
        
        EditorGUILayout.Space();
        
        // 导入模式选择
        string[] modes = { "手动输入", "CSV文件导入" };
        importMode = GUILayout.Toolbar(importMode, modes);
        
        EditorGUILayout.Space();

        if (importMode == 0)
        {
            DrawManualInputMode();
        }
        else
        {
            DrawCSVImportMode();
        }

        EditorGUILayout.Space();

        // 操作按钮
        DrawActionButtons();

        // 显示预览
        DrawPreview();
    }

    private void DrawManualInputMode()
    {
        GUILayout.Label("参数数据 (从表格复制粘贴):", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox("支持从Excel、Google Sheets等表格直接复制粘贴", MessageType.Info);
        
        scrollPos = EditorGUILayout.BeginScrollView(scrollPos, GUILayout.Height(200));
        parameterData = EditorGUILayout.TextArea(parameterData, GUILayout.ExpandHeight(true));
        EditorGUILayout.EndScrollView();
    }

    private void DrawCSVImportMode()
    {
        GUILayout.Label("CSV 文件导入:", EditorStyles.boldLabel);
        
        EditorGUILayout.BeginVertical("box");
        
        // CSV 文件选择
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField("CSV 文件路径:", GUILayout.Width(100));
        csvFilePath = EditorGUILayout.TextField(csvFilePath);
        if (GUILayout.Button("浏览...", GUILayout.Width(60)))
        {
            string path = EditorUtility.OpenFilePanel("选择CSV文件", Application.dataPath, "csv");
            if (!string.IsNullOrEmpty(path))
            {
                csvFilePath = path;
            }
        }
        EditorGUILayout.EndHorizontal();
        
        EditorGUILayout.Space(5);
        
        // CSV 导入设置
        GUILayout.Label("导入设置:", EditorStyles.miniBoldLabel);
        hasHeader = EditorGUILayout.Toggle("包含表头", hasHeader);
        
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField("分隔符:", GUILayout.Width(60));
        int delimiterChoice = EditorGUILayout.Popup(
            delimiter == ',' ? 0 : delimiter == '\t' ? 1 : delimiter == ';' ? 2 : 3,
            new string[] { "逗号 (,)", "制表符 (Tab)", "分号 (;)", "自定义" },
            GUILayout.Width(120)
        );
        
        switch (delimiterChoice)
        {
            case 0: delimiter = ','; break;
            case 1: delimiter = '\t'; break;
            case 2: delimiter = ';'; break;
            case 3:
                customDelimiter = EditorGUILayout.TextField(customDelimiter, GUILayout.Width(50));
                if (!string.IsNullOrEmpty(customDelimiter))
                    delimiter = customDelimiter[0];
                break;
        }
        EditorGUILayout.EndHorizontal();
        
        EditorGUILayout.Space(5);
        
        // 加载CSV按钮
        if (GUILayout.Button("加载 CSV 文件", GUILayout.Height(25)))
        {
            LoadCSVFile();
        }
        
        // 显示CSV文件信息
        if (!string.IsNullOrEmpty(csvFilePath) && File.Exists(csvFilePath))
        {
            EditorGUILayout.Space(5);
            FileInfo fileInfo = new FileInfo(csvFilePath);
            EditorGUILayout.LabelField("文件大小:", $"{fileInfo.Length / 1024f:F2} KB");
            EditorGUILayout.LabelField("修改时间:", fileInfo.LastWriteTime.ToString());
        }
        
        EditorGUILayout.EndVertical();
        
        // 预览CSV内容
        if (!string.IsNullOrEmpty(parameterData))
        {
            EditorGUILayout.Space(5);
            GUILayout.Label("CSV 文件预览:", EditorStyles.miniBoldLabel);
            scrollPos = EditorGUILayout.BeginScrollView(scrollPos, GUILayout.Height(150));
            EditorGUILayout.TextArea(parameterData, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
        }
    }

    private void DrawActionButtons()
    {
        EditorGUILayout.BeginHorizontal();
        
        GUI.backgroundColor = Color.cyan;
        if (GUILayout.Button("解析参数", GUILayout.Height(30)))
        {
            ParseParameters();
        }
        
        GUI.backgroundColor = Color.green;
        if (GUILayout.Button("应用到材质", GUILayout.Height(30)))
        {
            ApplyToMaterial();
        }
        
        GUI.backgroundColor = Color.yellow;
        if (GUILayout.Button("清空数据", GUILayout.Height(30)))
        {
            ClearData();
        }
        
        GUI.backgroundColor = Color.white;
        EditorGUILayout.EndHorizontal();
        
        // 批量操作按钮
        if (targetMaterial != null && parsedParameters.Count > 0)
        {
            EditorGUILayout.Space(5);
            EditorGUILayout.BeginHorizontal();
            
            GUI.backgroundColor = new Color(1f, 0.8f, 0.4f);
            if (GUILayout.Button("导出当前材质参数到CSV", GUILayout.Height(25)))
            {
                ExportMaterialToCSV();
            }
            
            GUI.backgroundColor = Color.white;
            EditorGUILayout.EndHorizontal();
        }
    }

    private void DrawPreview()
    {
        if (parsedParameters.Count > 0)
        {
            EditorGUILayout.Space();

            EditorGUILayout.BeginVertical("box");
            showPreview = EditorGUILayout.Foldout(showPreview,
                $"解析结果 ({parsedParameters.Count} 个参数, {parsedParameters.Count(p => p.willApply)} 个将被应用)",
                true, EditorStyles.foldoutHeader);

            if (showPreview)
            {
                EditorGUILayout.Space(5);

                // 统计信息
                int willApplyCount = parsedParameters.Count(p => p.willApply);
                int skipCount = parsedParameters.Count - willApplyCount;
                int stParameterCount = parsedParameters.Count(p =>
                    p.matchedPropertyName != null && p.matchedPropertyName.EndsWith("_ST"));

                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField($"✓ 匹配成功: {willApplyCount}", EditorStyles.boldLabel, GUILayout.Width(120));
                EditorGUILayout.LabelField($"✗ 未匹配: {skipCount}", GUILayout.Width(100));
                if (stParameterCount > 0)
                {
                    EditorGUILayout.LabelField($"🎨 纹理ST: {stParameterCount}", GUILayout.Width(100));
                }

                EditorGUILayout.EndHorizontal();

                EditorGUILayout.Space(5);

                previewScrollPos = EditorGUILayout.BeginScrollView(previewScrollPos, GUILayout.MaxHeight(300));

                foreach (var param in parsedParameters)
                {
                    Color originalBg = GUI.backgroundColor;
                    GUI.backgroundColor = param.willApply ? new Color(0.8f, 1f, 0.8f) : new Color(1f, 0.9f, 0.9f);

                    EditorGUILayout.BeginVertical("box");
                    GUI.backgroundColor = originalBg;

                    EditorGUILayout.BeginHorizontal();
                    EditorGUILayout.LabelField("参数名:", GUILayout.Width(60));
                    EditorGUILayout.LabelField(param.name, EditorStyles.boldLabel);
                    EditorGUILayout.EndHorizontal();

                    EditorGUILayout.BeginHorizontal();
                    EditorGUILayout.LabelField("值:", GUILayout.Width(60));
                    EditorGUILayout.LabelField(param.value);
                    EditorGUILayout.EndHorizontal();

                    EditorGUILayout.BeginHorizontal();
                    EditorGUILayout.LabelField("类型:", GUILayout.Width(60));
                    EditorGUILayout.LabelField(param.type);
                    EditorGUILayout.EndHorizontal();

                    if (param.willApply)
                    {
                        EditorGUILayout.BeginHorizontal();
                        EditorGUILayout.LabelField("匹配属性:", GUILayout.Width(60));

                        // **特别标注 _ST 参数**
                        string displayText = param.matchedPropertyName;
                        Color textColor = Color.green;

                        if (param.matchedPropertyName.EndsWith("_ST"))
                        {
                            displayText += " (Texture Scale/Offset)";
                            textColor = new Color(0.2f, 0.8f, 1f); // 青色
                        }

                        EditorGUILayout.LabelField(displayText, new GUIStyle(EditorStyles.label)
                        {
                            fontStyle = FontStyle.Bold,
                            normal = { textColor = textColor }
                        });
                        EditorGUILayout.EndHorizontal();
                    }
                    else
                    {
                        EditorGUILayout.LabelField("状态: 材质中无匹配属性", new GUIStyle(EditorStyles.helpBox)
                        {
                            normal = { textColor = Color.red }
                        });
                    }

                    EditorGUILayout.EndVertical();
                    EditorGUILayout.Space(3);
                }

                EditorGUILayout.EndScrollView();
            }

            EditorGUILayout.EndVertical();
        }
    }

    private void LoadCSVFile()
    {
        if (string.IsNullOrEmpty(csvFilePath))
        {
            EditorUtility.DisplayDialog("错误", "请先选择CSV文件", "确定");
            return;
        }

        if (!File.Exists(csvFilePath))
        {
            EditorUtility.DisplayDialog("错误", "文件不存在: " + csvFilePath, "确定");
            return;
        }

        try
        {
            parameterData = File.ReadAllText(csvFilePath);
            Debug.Log($"成功加载CSV文件: {csvFilePath}");
            EditorUtility.DisplayDialog("成功", "CSV文件加载成功！\n请点击'解析参数'继续。", "确定");
        }
        catch (System.Exception e)
        {
            EditorUtility.DisplayDialog("错误", $"读取CSV文件失败:\n{e.Message}", "确定");
            Debug.LogError($"读取CSV文件失败: {e}");
        }
    }

    private void ParseParameters()
    {
        parsedParameters.Clear();

        if (string.IsNullOrEmpty(parameterData))
        {
            EditorUtility.DisplayDialog("错误", "请输入参数数据或加载CSV文件", "确定");
            return;
        }

        string[] lines = parameterData.Split('\n');
        int startIndex = (hasHeader && importMode == 1) ? 1 : 0; // CSV模式下跳过表头

        
        for (int i = startIndex; i < lines.Length; i++)
        {
            string line = lines[i];
            if (string.IsNullOrWhiteSpace(line)) continue;
            
            // 根据模式使用不同的分隔符
            char currentDelimiter = importMode == 1 ? delimiter : '\t';
            string[] parts = ParseCSVLine(line, currentDelimiter);
            
            if (parts.Length >= 2) // 至少需要名称和值
            {
                ParameterInfo param = new ParameterInfo
                {
                    name = parts[0].Trim(),
                    value = parts[1].Trim(),
                    type = parts.Length >= 3 ? parts[parts.Length>3?3:2].Trim() : "float" // 默认类型
                };

                // 跳过表头行（手动输入模式）
                if (param.name.ToLower() == "name" || param.name.ToLower() == "参数名")
                    continue;

                // 检查是否能匹配材质属性
                if (targetMaterial != null)
                {
                    string matchedProp = FindMatchingProperty(param.name);
                    if (!string.IsNullOrEmpty(matchedProp))
                    {
                        param.willApply = true;
                        param.matchedPropertyName = matchedProp;
                    }
                }

                parsedParameters.Add(param);
            }
        }

        Debug.Log($"解析完成，共 {parsedParameters.Count} 个参数，其中 {parsedParameters.Count(p => p.willApply)} 个可以应用");
        
        if (parsedParameters.Count == 0)
        {
            EditorUtility.DisplayDialog("提示", "未能解析出任何参数，请检查数据格式", "确定");
        }
    }

    private string[] ParseCSVLine(string line, char delimiter)
    {
        List<string> result = new List<string>();
        bool inQuotes = false;
        string currentField = "";

        for (int i = 0; i < line.Length; i++)
        {
            char c = line[i];

            if (c == '"')
            {
                inQuotes = !inQuotes;
            }
            else if (c == delimiter && !inQuotes)
            {
                result.Add(currentField);
                currentField = "";
            }
            else
            {
                currentField += c;
            }
        }

        result.Add(currentField);
        return result.ToArray();
    }

    private string FindMatchingProperty(string paramName)
    {
        // if (targetMaterial == null) return null;
        //
        // Shader shader = targetMaterial.shader;
        // int propertyCount = ShaderUtil.GetPropertyCount(shader);
        //
        // // 提取参数名中 _ 后面的部分
        // string suffix = GetSuffixAfterUnderscore(paramName);
        // if (string.IsNullOrEmpty(suffix)) return null;
        //
        // for (int i = 0; i < propertyCount; i++)
        // {
        //     string propertyName = ShaderUtil.GetPropertyName(shader, i);
        //     string propertySuffix = GetSuffixAfterUnderscore(propertyName);
        //
        //     // 比较后缀是否一致
        //     if (!string.IsNullOrEmpty(propertySuffix) && 
        //         suffix.Equals(propertySuffix, System.StringComparison.OrdinalIgnoreCase))
        //     {
        //         return propertyName;
        //     }
        // }
        //
        // return null;
        if (targetMaterial == null) return null;

        Shader shader = targetMaterial.shader;
        int propertyCount = ShaderUtil.GetPropertyCount(shader);

        // 提取参数名中 _ 后面的部分
        string suffix = GetSuffixAfterUnderscore(paramName);
        if (string.IsNullOrEmpty(suffix)) return null;

        // **检查是否是 _ST 参数（纹理的 Scale/Offset）**
        bool isSTParameter = suffix.EndsWith("_ST");
        string textureSuffix = null;

        if (isSTParameter)
        {
            // 提取纹理名部分，例如 "MainTex_ST" -> "MainTex"
            textureSuffix = suffix.Substring(0, suffix.Length - 3);
        }

        for (int i = 0; i < propertyCount; i++)
        {
            string propertyName = ShaderUtil.GetPropertyName(shader, i);
            ShaderUtil.ShaderPropertyType propertyType = ShaderUtil.GetPropertyType(shader, i);
            string propertySuffix = GetSuffixAfterUnderscore(propertyName);

            // **情况1: 匹配 _ST 参数**
            if (isSTParameter && propertyType == ShaderUtil.ShaderPropertyType.TexEnv)
            {
                // 比较纹理名部分是否匹配
                // 例如: Material_MainTex_ST 的 textureSuffix="MainTex" 
                //       与 _MainTex 的 propertySuffix="MainTex" 匹配
                if (!string.IsNullOrEmpty(propertySuffix) &&
                    textureSuffix.Equals(propertySuffix, System.StringComparison.OrdinalIgnoreCase))
                {
                    // 返回对应的 _ST 属性名
                    return propertyName + "_ST";
                }
            }
            // **情况2: 普通参数匹配**
            else if (!isSTParameter)
            {
                // 比较后缀是否一致
                if (!string.IsNullOrEmpty(propertySuffix) &&
                    suffix.Equals(propertySuffix, System.StringComparison.OrdinalIgnoreCase))
                {
                    return propertyName;
                }
            }
        }

        // **情况3: 如果是 _ST 参数但没有找到对应纹理，尝试直接匹配 _ST 属性**
        if (isSTParameter)
        {
            // 检查材质是否直接有这个 _ST 属性（作为 Vector）
            for (int i = 0; i < propertyCount; i++)
            {
                string propertyName = ShaderUtil.GetPropertyName(shader, i);
                string propertySuffix = GetSuffixAfterUnderscore(propertyName);

                if (!string.IsNullOrEmpty(propertySuffix) &&
                    suffix.Equals(propertySuffix, System.StringComparison.OrdinalIgnoreCase))
                {
                    return propertyName;
                }
            }
        }

        return null;
    }

    private string GetSuffixAfterUnderscore(string name)
    {
        //int lastUnderscoreIndex = name.LastIndexOf('_'); 忽略首次_
        int lastUnderscoreIndex = name.IndexOf('_');
        if (lastUnderscoreIndex >= 0 && lastUnderscoreIndex < name.Length - 1)
        {
            return name.Substring(lastUnderscoreIndex + 1);
        }
        return name;
    }

    private void ApplyToMaterial()
    {
        if (targetMaterial == null)
        {
            EditorUtility.DisplayDialog("错误", "请先选择目标材质", "确定");
            return;
        }

        if (parsedParameters.Count == 0)
        {
            EditorUtility.DisplayDialog("错误", "请先解析参数数据", "确定");
            return;
        }

        Undo.RecordObject(targetMaterial, "Apply Material Parameters");

        int successCount = 0;
        int skipCount = 0;

        foreach (var param in parsedParameters)
        {
            if (!param.willApply) 
            {
                skipCount++;
                continue;
            }

            try
            {
                if (SetMaterialProperty(targetMaterial, param))
                {
                    successCount++;
                    Debug.Log($"✓ 成功设置: {param.matchedPropertyName} = {param.value}");
                }
                else
                {
                    skipCount++;
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError($"✗ 设置参数 {param.name} 失败: {e.Message}");
                skipCount++;
            }
        }

        EditorUtility.SetDirty(targetMaterial);
        AssetDatabase.SaveAssets();

        EditorUtility.DisplayDialog("完成", 
            $"参数应用完成！\n\n✓ 成功: {successCount}\n✗ 跳过: {skipCount}", 
            "确定");
    }
    // **新增方法：处理纹理的 Scale 和 Offset**
    private bool SetTextureScaleOffset(Material mat, string stPropertyName, string value)
    {
        // 从 _MainTex_ST 提取 _MainTex
        string textureName = stPropertyName.Substring(0, stPropertyName.Length - 3);
    
        try
        {
            // 解析 Vector4: (scaleX, scaleY, offsetX, offsetY)
            Vector4 stValue = ParseVector4(value);
        
            // 优先使用 SetTextureScale 和 SetTextureOffset
            Vector2 scale = new Vector2(stValue.x, stValue.y);
            Vector2 offset = new Vector2(stValue.z, stValue.w);
        
            // **方法1: 如果纹理属性存在，使用专用方法**
            if (mat.HasProperty(textureName))
            {
                mat.SetTextureScale(textureName, scale);
                mat.SetTextureOffset(textureName, offset);
                Debug.Log($"✓ 设置纹理参数: {textureName} Scale={scale}, Offset={offset}");
            }
            // **方法2: 如果 _ST 作为 Vector4 属性存在，直接设置**
            else if (mat.HasProperty(stPropertyName))
            {
                mat.SetVector(stPropertyName, stValue);
                Debug.Log($"✓ 设置向量参数: {stPropertyName} = {stValue}");
            }
            else
            {
                Debug.LogWarning($"未找到纹理属性 {textureName} 或向量属性 {stPropertyName}");
                return false;
            }
        
            return true;
        }
        catch (System.Exception e)
        {
            Debug.LogError($"设置 {stPropertyName} 失败: {e.Message}");
            return false;
        }
    }
    private bool SetMaterialProperty(Material mat, ParameterInfo param)
    {
        string propertyName = param.matchedPropertyName;

        // **特殊处理 _ST 参数（纹理的 Scale 和 Offset）**
        if (propertyName.EndsWith("_ST"))
        {
            return SetTextureScaleOffset(mat, propertyName, param.value);
        }
        
        if (!mat.HasProperty(propertyName))
        {
            return false;
        }
        
        // 根据类型设置属性
        if (param.type.ToLower().Contains("float4")|| param.type.ToLower().Contains("float3") || param.type.ToLower().Contains("color") || param.type.ToLower().Contains("vector"))
        {
            Vector4 vector = ParseVector4(param.value);
            mat.SetVector(propertyName, vector);
            // 如果是颜色属性，也尝试设置为Color
            if (mat.HasProperty(propertyName))
            {
                mat.SetColor(propertyName, new Color(vector.x, vector.y, vector.z, vector.w));
            }
            return true;
        }
        else if (param.type.ToLower().Contains("float") || param.type.ToLower().Contains("int"))
        {
            float floatValue = ParseFloat(param.value);
            mat.SetFloat(propertyName, floatValue);
            return true;
        }
        else if (param.type.ToLower().Contains(""))
        { 
            
        }

        return false;
    }

    private Vector4 ParseVector4(string value)
    {
        // 移除多余的空格和括号，分割数字
        value = value.Replace("(", "").Replace(")", "").Replace("[", "").Replace("]", "");
        string[] parts = value.Split(new char[] { ',', ' ', ';' }, System.StringSplitOptions.RemoveEmptyEntries);
        
        Vector4 result = Vector4.zero;
        
        if (parts.Length >= 1) float.TryParse(parts[0], out result.x);
        if (parts.Length >= 2) float.TryParse(parts[1], out result.y);
        if (parts.Length >= 3) float.TryParse(parts[2], out result.z);
        if (parts.Length >= 4) float.TryParse(parts[3], out result.w);
        
        return result;
    }

    private float ParseFloat(string value)
    {
        float result = 0f;
        // 移除可能的单位或其他字符
        value = value.Trim().Split(' ')[0];
        float.TryParse(value, out result);
        return result;
    }

    private void ClearData()
    {
        if (EditorUtility.DisplayDialog("确认", "确定要清空所有数据吗？", "确定", "取消"))
        {
            parameterData = "";
            parsedParameters.Clear();
            csvFilePath = "";
            Debug.Log("数据已清空");
        }
    }

    private void ExportMaterialToCSV()
    {
        if (targetMaterial == null)
        {
            EditorUtility.DisplayDialog("错误", "请先选择目标材质", "确定");
            return;
        }

        string path = EditorUtility.SaveFilePanel("导出材质参数到CSV", Application.dataPath, 
            targetMaterial.name + "_parameters", "csv");
        
        if (string.IsNullOrEmpty(path)) return;

        try
        {
            using (StreamWriter writer = new StreamWriter(path))
            {
                // 写入表头
                writer.WriteLine("Name,Value,Type");

                Shader shader = targetMaterial.shader;
                int propertyCount = ShaderUtil.GetPropertyCount(shader);

                for (int i = 0; i < propertyCount; i++)
                {
                    string propertyName = ShaderUtil.GetPropertyName(shader, i);
                    ShaderUtil.ShaderPropertyType propertyType = ShaderUtil.GetPropertyType(shader, i);

                    string value = "";
                    string type = "";

                    switch (propertyType)
                    {
                        case ShaderUtil.ShaderPropertyType.Color:
                            Color color = targetMaterial.GetColor(propertyName);
                            value = $"{color.r:F2}, {color.g:F2}, {color.b:F2}, {color.a:F2}";
                            type = "float4";
                            break;
                        case ShaderUtil.ShaderPropertyType.Vector:
                            Vector4 vector = targetMaterial.GetVector(propertyName);
                            value = $"{vector.x:F2}, {vector.y:F2}, {vector.z:F2}, {vector.w:F2}";
                            type = "float4";
                            break;
                        case ShaderUtil.ShaderPropertyType.Float:
                        case ShaderUtil.ShaderPropertyType.Range:
                            float floatVal = targetMaterial.GetFloat(propertyName);
                            value = floatVal.ToString("F2");
                            type = "float";
                            break;
                        case ShaderUtil.ShaderPropertyType.TexEnv:
                            // **导出纹理的 Scale 和 Offset**
                            Vector2 scale = targetMaterial.GetTextureScale(propertyName);
                            Vector2 offset = targetMaterial.GetTextureOffset(propertyName);
                            if (scale != Vector2.one || offset != Vector2.zero)
                            {
                                // 导出 _ST 参数
                                string stName = propertyName + "_ST";
                                string stValue = $"{scale.x:F4}, {scale.y:F4}, {offset.x:F4}, {offset.y:F4}";
                                writer.WriteLine($"{stName},{stValue},float4");
                            }
                            continue; // 跳过纹理
                    }

                    writer.WriteLine($"{propertyName},{value},{type}");
                }
            }

            EditorUtility.DisplayDialog("成功", $"材质参数已导出到:\n{path}", "确定");
            Debug.Log($"材质参数已导出到: {path}");
        }
        catch (System.Exception e)
        {
            EditorUtility.DisplayDialog("错误", $"导出失败:\n{e.Message}", "确定");
            Debug.LogError($"导出CSV失败: {e}");
        }
    }
}
