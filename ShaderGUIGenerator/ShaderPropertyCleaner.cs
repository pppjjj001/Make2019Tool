using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using System.Linq;

public class ShaderPropertyCleanerPro : EditorWindow
{
    #region 数据结构
    
    [System.Serializable]
    public class PropertyInfo
    {
        public string fullLine;           // 完整行内容
        public string propertyName;       // 属性名 如 _UseJizhi3
        public string originalDisplay;    // 原始显示名
        public string newDisplay;         // 新显示名
        public int lineNumber;
        public bool hasNonEnglish;
        public bool willBeFixed;
    }

    [System.Serializable]
    public class ShaderAnalysis
    {
        public string shaderPath;
        public string shaderName;
        public List<PropertyInfo> properties = new List<PropertyInfo>();
        public bool hasIssues;
        public bool isExpanded = true;
        public bool isSelected = true;
        public bool isManualAdded = false;  // 是否手动添加
    }
    
    #endregion

    #region 成员变量
    
    private List<ShaderAnalysis> analysisResults = new List<ShaderAnalysis>();
    private List<Shader> manualShaderList = new List<Shader>();  // 手动添加的Shader列表
    private Vector2 scrollPosition;
    private Vector2 manualListScrollPos;
    private string searchFolder = "Assets";
    private bool includeSubfolders = true;
    private bool showOnlyIssues = true;
    private int totalShadersScanned = 0;
    private int totalIssuesFound = 0;
    
    // 界面状态
    private bool showManualList = true;
    private bool showScanSettings = true;
    private Shader shaderToAdd;
    
    // 改进的正则表达式 - 支持多个属性标记 [Enum(...)][Space(5)][Header(...)]
    private static readonly Regex PropertyRegex = new Regex(
        @"^\s*((?:\[[^\]]+\]\s*)*)(_?\w+)\s*\(\s*""([^""]*)""\s*,",
        RegexOptions.Compiled
    );
    
    // 非英文字符检测（检测非ASCII字符）
    private static readonly Regex NonEnglishRegex = new Regex(
        @"[^\x00-\x7F]",
        RegexOptions.Compiled
    );
    
    // 用于测试的额外正则 - 更宽松的匹配
    private static readonly Regex LoosePropertyRegex = new Regex(
        @"(_\w+)\s*\(\s*""([^""]+)""\s*,\s*(\w+)",
        RegexOptions.Compiled
    );

    #endregion

    [MenuItem("Tools/TempByAI/Shader/属性名称清理工具 Pro")]
    public static void ShowWindow()
    {
        var window = GetWindow<ShaderPropertyCleanerPro>("Shader属性清理 Pro");
        window.minSize = new Vector2(700, 500);
    }

    #region GUI绘制
    
    private void OnGUI()
    {
        EditorGUILayout.Space(5);
        
        // 标题
        DrawHeader();
        
        EditorGUILayout.Space(5);
        
        // 手动Shader列表区域
        DrawManualShaderList();
        
        EditorGUILayout.Space(5);
        
        // 扫描设置区域
        DrawScanSettings();
        
        EditorGUILayout.Space(5);
        
        // 操作按钮
        DrawActionButtons();
        
        EditorGUILayout.Space(5);
        
        // 统计信息
        if (analysisResults.Count > 0)
        {
            DrawStatistics();
        }
        
        EditorGUILayout.Space(5);
        
        // 结果列表
        DrawResultsList();
        
        // 处理拖拽
        HandleDragAndDrop();
    }

    private void DrawHeader()
    {
        EditorGUILayout.BeginHorizontal();
        GUILayout.Label("Shader 属性显示名称清理工具 Pro", EditorStyles.boldLabel);
        GUILayout.FlexibleSpace();
        if (GUILayout.Button("?", GUILayout.Width(25)))
        {
            ShowHelp();
        }
        EditorGUILayout.EndHorizontal();
        
        EditorGUILayout.HelpBox(
            "检测并修复Shader属性中的非英文显示名称。支持复杂属性标记如:\n" +
            "[Enum(OFF,0,ON,1)][Space(5)][Header(xxx)]_Prop(\"中文名\", Float) = 0", 
            MessageType.Info
        );
    }

    private void DrawManualShaderList()
    {
        showManualList = EditorGUILayout.BeginFoldoutHeaderGroup(showManualList, 
            $"📋 手动Shader列表 ({manualShaderList.Count})");
        
        if (showManualList)
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            // 添加Shader
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("添加Shader:", GUILayout.Width(80));
            shaderToAdd = (Shader)EditorGUILayout.ObjectField(shaderToAdd, typeof(Shader), false);
            
            GUI.enabled = shaderToAdd != null;
            if (GUILayout.Button("添加", GUILayout.Width(50)))
            {
                AddShaderToManualList(shaderToAdd);
                shaderToAdd = null;
            }
            GUI.enabled = true;
            
            if (GUILayout.Button("添加选中", GUILayout.Width(70)))
            {
                AddSelectedShaders();
            }
            EditorGUILayout.EndHorizontal();
            
            // 拖拽提示
            Rect dropArea = GUILayoutUtility.GetRect(0, 40, GUILayout.ExpandWidth(true));
            GUI.Box(dropArea, "🎯 拖拽 Shader 文件到此处添加", EditorStyles.helpBox);
            
            // 显示已添加的Shader列表
            if (manualShaderList.Count > 0)
            {
                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("已添加的Shader:", EditorStyles.boldLabel);
                
                manualListScrollPos = EditorGUILayout.BeginScrollView(manualListScrollPos, 
                    GUILayout.MaxHeight(100));
                
                for (int i = manualShaderList.Count - 1; i >= 0; i--)
                {
                    EditorGUILayout.BeginHorizontal();
                    
                    if (manualShaderList[i] == null)
                    {
                        manualShaderList.RemoveAt(i);
                        continue;
                    }
                    
                    EditorGUILayout.ObjectField(manualShaderList[i], typeof(Shader), false);
                    
                    if (GUILayout.Button("×", GUILayout.Width(25)))
                    {
                        manualShaderList.RemoveAt(i);
                    }
                    
                    EditorGUILayout.EndHorizontal();
                }
                
                EditorGUILayout.EndScrollView();
                
                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("清空列表"))
                {
                    manualShaderList.Clear();
                }
                if (GUILayout.Button("仅分析列表中的Shader"))
                {
                    AnalyzeManualListOnly();
                }
                EditorGUILayout.EndHorizontal();
            }
            
            EditorGUILayout.EndVertical();
        }
        EditorGUILayout.EndFoldoutHeaderGroup();
    }

    private void DrawScanSettings()
    {
        showScanSettings = EditorGUILayout.BeginFoldoutHeaderGroup(showScanSettings, "⚙️ 文件夹扫描设置");
        
        if (showScanSettings)
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("扫描文件夹:", GUILayout.Width(80));
            searchFolder = EditorGUILayout.TextField(searchFolder);
            if (GUILayout.Button("选择", GUILayout.Width(50)))
            {
                string path = EditorUtility.OpenFolderPanel("选择文件夹", searchFolder, "");
                if (!string.IsNullOrEmpty(path))
                {
                    if (path.StartsWith(Application.dataPath))
                    {
                        searchFolder = "Assets" + path.Substring(Application.dataPath.Length);
                    }
                }
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.BeginHorizontal();
            includeSubfolders = EditorGUILayout.Toggle("包含子文件夹", includeSubfolders);
            showOnlyIssues = EditorGUILayout.Toggle("仅显示有问题的", showOnlyIssues);
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.EndVertical();
        }
        EditorGUILayout.EndFoldoutHeaderGroup();
    }

    private void DrawActionButtons()
    {
        EditorGUILayout.BeginHorizontal();
        
        // 分析按钮
        GUI.backgroundColor = new Color(0.6f, 0.8f, 1f);
        if (GUILayout.Button("🔍 分析全部\n(文件夹+列表)", GUILayout.Height(40)))
        {
            AnalyzeAll();
        }
        
        // 修复按钮
        GUI.backgroundColor = new Color(0.6f, 1f, 0.6f);
        GUI.enabled = totalIssuesFound > 0;
        if (GUILayout.Button("✓ 应用选中修复", GUILayout.Height(40)))
        {
            ApplySelectedFixes();
        }
        
        GUI.backgroundColor = new Color(1f, 0.8f, 0.6f);
        if (GUILayout.Button("✓ 修复全部问题", GUILayout.Height(40)))
        {
            ApplyAllFixes();
        }
        GUI.enabled = true;
        
        // 工具按钮
        GUI.backgroundColor = Color.white;
        EditorGUILayout.BeginVertical(GUILayout.Width(80));
        if (GUILayout.Button("清除结果", GUILayout.Height(18)))
        {
            ClearResults();
        }
        if (GUILayout.Button("测试正则", GUILayout.Height(18)))
        {
            ShowRegexTester();
        }
        EditorGUILayout.EndVertical();
        
        GUI.backgroundColor = Color.white;
        EditorGUILayout.EndHorizontal();
    }

    private void DrawStatistics()
    {
        EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);
        
        GUILayout.Label($"📊 统计:", EditorStyles.boldLabel, GUILayout.Width(50));
        GUILayout.Label($"Shader: {totalShadersScanned}");
        GUILayout.Label($"有问题: {analysisResults.Count(a => a.hasIssues)}");
        
        var totalProps = analysisResults.Sum(a => a.properties.Count(p => p.hasNonEnglish));
        GUILayout.Label($"问题属性: {totalProps}");
        
        GUILayout.FlexibleSpace();
        
        // 全选/取消全选
        if (GUILayout.Button("全选", GUILayout.Width(50)))
        {
            foreach (var a in analysisResults.Where(x => x.hasIssues))
            {
                a.isSelected = true;
                foreach (var p in a.properties) p.willBeFixed = p.hasNonEnglish;
            }
        }
        if (GUILayout.Button("取消全选", GUILayout.Width(60)))
        {
            foreach (var a in analysisResults)
            {
                a.isSelected = false;
                foreach (var p in a.properties) p.willBeFixed = false;
            }
        }
        
        EditorGUILayout.EndHorizontal();
    }

    private void DrawResultsList()
    {
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        
        EditorGUILayout.BeginHorizontal();
        GUILayout.Label("📝 分析结果预览", EditorStyles.boldLabel);
        GUILayout.FlexibleSpace();
        EditorGUILayout.EndHorizontal();
        
        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);
        
        int displayedCount = 0;
        foreach (var analysis in analysisResults)
        {
            if (showOnlyIssues && !analysis.hasIssues)
                continue;
            
            displayedCount++;
            DrawShaderAnalysis(analysis);
        }
        
        if (displayedCount == 0)
        {
            if (analysisResults.Count == 0)
            {
                EditorGUILayout.HelpBox("点击 \"分析全部\" 或 \"仅分析列表中的Shader\" 开始检测", MessageType.None);
            }
            else
            {
                EditorGUILayout.HelpBox("没有发现问题! 所有Shader属性名称都是英文。", MessageType.Info);
            }
        }
        
        EditorGUILayout.EndScrollView();
        EditorGUILayout.EndVertical();
    }

    private void DrawShaderAnalysis(ShaderAnalysis analysis)
    {
        Color bgColor = analysis.hasIssues ? new Color(1f, 0.92f, 0.85f) : new Color(0.85f, 1f, 0.85f);
        GUI.backgroundColor = bgColor;
        
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        GUI.backgroundColor = Color.white;
        
        // 标题行
        EditorGUILayout.BeginHorizontal();
        
        // 折叠箭头
        analysis.isExpanded = EditorGUILayout.Foldout(analysis.isExpanded, "", true, GUIStyle.none);
        
        // 选中框
        if (analysis.hasIssues)
        {
            bool newSelected = EditorGUILayout.Toggle(analysis.isSelected, GUILayout.Width(20));
            if (newSelected != analysis.isSelected)
            {
                analysis.isSelected = newSelected;
                foreach (var prop in analysis.properties)
                {
                    prop.willBeFixed = newSelected && prop.hasNonEnglish;
                }
            }
        }
        
        // 图标和名称
        string icon = analysis.hasIssues ? "⚠️" : "✓";
        string manualTag = analysis.isManualAdded ? " [手动]" : "";
        GUIStyle nameStyle = new GUIStyle(EditorStyles.boldLabel);
        if (analysis.hasIssues) nameStyle.normal.textColor = new Color(0.8f, 0.4f, 0f);
        GUILayout.Label($"{icon} {analysis.shaderName}{manualTag}", nameStyle);
        
        GUILayout.FlexibleSpace();
        
        // 问题数量
        if (analysis.hasIssues)
        {
            int issueCount = analysis.properties.Count(p => p.hasNonEnglish);
            GUILayout.Label($"[{issueCount} 问题]", EditorStyles.miniLabel);
        }
        
        // 操作按钮
        if (GUILayout.Button("定位", GUILayout.Width(40)))
        {
            PingShader(analysis.shaderPath);
        }
        if (GUILayout.Button("打开", GUILayout.Width(40)))
        {
            OpenShaderFile(analysis.shaderPath);
        }
        
        EditorGUILayout.EndHorizontal();
        
        // 路径显示
        if (analysis.isExpanded)
        {
            EditorGUI.indentLevel++;
            EditorGUILayout.LabelField("路径:", analysis.shaderPath, EditorStyles.miniLabel);
            
            // 属性列表
            if (analysis.properties.Count > 0)
            {
                EditorGUILayout.Space(3);
                
                // 表头
                EditorGUILayout.BeginHorizontal();
                GUILayout.Space(20);
                GUILayout.Label("行", EditorStyles.miniLabel, GUILayout.Width(35));
                GUILayout.Label("属性名", EditorStyles.miniLabel, GUILayout.Width(140));
                GUILayout.Label("原始显示名", EditorStyles.miniLabel, GUILayout.Width(150));
                GUILayout.Label("", GUILayout.Width(25));
                GUILayout.Label("新显示名", EditorStyles.miniLabel, GUILayout.Width(150));
                EditorGUILayout.EndHorizontal();
                
                foreach (var prop in analysis.properties)
                {
                    if (!prop.hasNonEnglish && showOnlyIssues)
                        continue;
                        
                    DrawPropertyInfo(prop, analysis);
                }
            }
            
            EditorGUI.indentLevel--;
        }
        
        EditorGUILayout.EndVertical();
        EditorGUILayout.Space(2);
    }

    private void DrawPropertyInfo(PropertyInfo prop, ShaderAnalysis parent)
    {
        EditorGUILayout.BeginHorizontal();
        
        GUILayout.Space(20);
        
        // 修复选择框
        if (prop.hasNonEnglish)
        {
            bool newFix = EditorGUILayout.Toggle(prop.willBeFixed, GUILayout.Width(20));
            if (newFix != prop.willBeFixed)
            {
                prop.willBeFixed = newFix;
                parent.isSelected = parent.properties.Any(p => p.willBeFixed);
            }
        }
        else
        {
            GUILayout.Space(24);
        }
        
        // 行号
        GUILayout.Label($"L{prop.lineNumber}", EditorStyles.miniLabel, GUILayout.Width(35));
        
        // 属性名
        GUILayout.Label(prop.propertyName, EditorStyles.boldLabel, GUILayout.Width(140));
        
        // 原始显示名
        if (prop.hasNonEnglish)
        {
            GUI.color = new Color(1f, 0.5f, 0.5f);
        }
        GUILayout.Label($"\"{prop.originalDisplay}\"", GUILayout.Width(150));
        GUI.color = Color.white;
        
        // 箭头
        if (prop.hasNonEnglish)
        {
            GUILayout.Label("→", GUILayout.Width(25));
            
            // 新显示名（可编辑）
            GUI.color = new Color(0.5f, 1f, 0.5f);
            prop.newDisplay = EditorGUILayout.TextField(prop.newDisplay, GUILayout.Width(150));
            GUI.color = Color.white;
        }
        
        GUILayout.FlexibleSpace();
        EditorGUILayout.EndHorizontal();
    }

    #endregion

    #region 拖拽处理
    
    private void HandleDragAndDrop()
    {
        Event evt = Event.current;
        
        if (evt.type == EventType.DragUpdated || evt.type == EventType.DragPerform)
        {
            // 检查是否有Shader文件
            bool hasShader = DragAndDrop.objectReferences.Any(o => o is Shader);
            bool hasShaderFile = DragAndDrop.paths.Any(p => p.EndsWith(".shader"));
            
            if (hasShader || hasShaderFile)
            {
                DragAndDrop.visualMode = DragAndDropVisualMode.Copy;
                
                if (evt.type == EventType.DragPerform)
                {
                    DragAndDrop.AcceptDrag();
                    
                    foreach (var obj in DragAndDrop.objectReferences)
                    {
                        if (obj is Shader shader)
                        {
                            AddShaderToManualList(shader);
                        }
                    }
                    
                    foreach (var path in DragAndDrop.paths)
                    {
                        if (path.EndsWith(".shader"))
                        {
                            var shader = AssetDatabase.LoadAssetAtPath<Shader>(path);
                            if (shader != null)
                            {
                                AddShaderToManualList(shader);
                            }
                        }
                    }
                }
                
                evt.Use();
            }
        }
    }
    
    #endregion

    #region Shader列表管理
    
    private void AddShaderToManualList(Shader shader)
    {
        if (shader == null) return;
        
        if (!manualShaderList.Contains(shader))
        {
            manualShaderList.Add(shader);
            Debug.Log($"[ShaderCleaner] 添加Shader: {shader.name}");
        }
    }
    
    private void AddSelectedShaders()
    {
        foreach (var obj in Selection.objects)
        {
            if (obj is Shader shader)
            {
                AddShaderToManualList(shader);
            }
        }
        
        // 也检查选中的文件
        foreach (var guid in Selection.assetGUIDs)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            if (path.EndsWith(".shader"))
            {
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(path);
                if (shader != null)
                {
                    AddShaderToManualList(shader);
                }
            }
        }
    }
    
    #endregion

    #region 分析功能
    
    private void AnalyzeAll()
    {
        analysisResults.Clear();
        totalShadersScanned = 0;
        totalIssuesFound = 0;
        
        EditorUtility.DisplayProgressBar("分析Shader", "正在扫描...", 0);
        
        try
        {
            // 分析文件夹中的Shader
            AnalyzeFolderShaders();
            
            // 分析手动添加的Shader
            AnalyzeManualShaders();
            
            // 去重（根据路径）
            analysisResults = analysisResults
                .GroupBy(a => a.shaderPath)
                .Select(g => g.First())
                .ToList();
            
            // 排序
            analysisResults = analysisResults
                .OrderByDescending(a => a.hasIssues)
                .ThenBy(a => a.shaderName)
                .ToList();
            
            totalShadersScanned = analysisResults.Count;
            totalIssuesFound = analysisResults.Sum(a => a.properties.Count(p => p.hasNonEnglish));
        }
        finally
        {
            EditorUtility.ClearProgressBar();
        }
        
        Debug.Log($"[ShaderCleaner] 扫描完成: {totalShadersScanned} 个Shader, {totalIssuesFound} 个问题");
    }
    
    private void AnalyzeManualListOnly()
    {
        analysisResults.Clear();
        totalShadersScanned = 0;
        totalIssuesFound = 0;
        
        EditorUtility.DisplayProgressBar("分析Shader", "正在分析列表...", 0);
        
        try
        {
            AnalyzeManualShaders();
            
            analysisResults = analysisResults
                .OrderByDescending(a => a.hasIssues)
                .ThenBy(a => a.shaderName)
                .ToList();
            
            totalShadersScanned = analysisResults.Count;
            totalIssuesFound = analysisResults.Sum(a => a.properties.Count(p => p.hasNonEnglish));
        }
        finally
        {
            EditorUtility.ClearProgressBar();
        }
        
        Debug.Log($"[ShaderCleaner] 列表分析完成: {totalShadersScanned} 个Shader, {totalIssuesFound} 个问题");
    }
    
    private void AnalyzeFolderShaders()
    {
        string fullPath = Path.Combine(Directory.GetCurrentDirectory(), searchFolder);
        
        if (!Directory.Exists(fullPath))
        {
            Debug.LogWarning($"[ShaderCleaner] 文件夹不存在: {searchFolder}");
            return;
        }
        
        SearchOption searchOption = includeSubfolders ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
        string[] shaderFiles = Directory.GetFiles(fullPath, "*.shader", searchOption);
        
        for (int i = 0; i < shaderFiles.Length; i++)
        {
            EditorUtility.DisplayProgressBar("分析Shader", 
                Path.GetFileName(shaderFiles[i]), (float)i / shaderFiles.Length);
            
            var analysis = AnalyzeSingleShader(shaderFiles[i], false);
            if (analysis != null)
            {
                analysisResults.Add(analysis);
            }
        }
    }
    
    private void AnalyzeManualShaders()
    {
        for (int i = 0; i < manualShaderList.Count; i++)
        {
            if (manualShaderList[i] == null) continue;
            
            string path = AssetDatabase.GetAssetPath(manualShaderList[i]);
            if (string.IsNullOrEmpty(path)) continue;
            
            EditorUtility.DisplayProgressBar("分析Shader", 
                manualShaderList[i].name, (float)i / manualShaderList.Count);
            
            string fullPath = Path.Combine(Directory.GetCurrentDirectory(), path);
            var analysis = AnalyzeSingleShader(fullPath, true);
            if (analysis != null)
            {
                analysisResults.Add(analysis);
            }
        }
    }

    private ShaderAnalysis AnalyzeSingleShader(string filePath, bool isManual)
    {
        string relativePath = GetRelativePath(filePath);
        
        var analysis = new ShaderAnalysis
        {
            shaderPath = relativePath,
            shaderName = Path.GetFileNameWithoutExtension(filePath),
            isManualAdded = isManual
        };
        
        try
        {
            string[] lines = File.ReadAllLines(filePath);
            bool inPropertiesBlock = false;
            int braceCount = 0;
            
            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];
                string trimmedLine = line.Trim();
                
                // 跳过注释行
                if (trimmedLine.StartsWith("//"))
                    continue;
                
                // 检测Properties块开始
                if (trimmedLine.StartsWith("Properties"))
                {
                    inPropertiesBlock = true;
                    braceCount = 0;
                }
                
                if (inPropertiesBlock)
                {
                    braceCount += line.Count(c => c == '{');
                    braceCount -= line.Count(c => c == '}');
                    
                    // Properties块结束
                    if (braceCount <= 0 && line.Contains("}"))
                    {
                        inPropertiesBlock = false;
                        continue;
                    }
                    
                    // 尝试匹配属性行 - 使用改进的正则
                    var match = PropertyRegex.Match(trimmedLine);
                    if (!match.Success)
                    {
                        // 尝试更宽松的匹配
                        match = LoosePropertyRegex.Match(trimmedLine);
                    }
                    
                    if (match.Success)
                    {
                        string propertyName = "";
                        string displayName = "";
                        
                        // 根据匹配的正则获取对应的组
                        if (match.Groups.Count >= 4)
                        {
                            // PropertyRegex 匹配
                            propertyName = match.Groups[2].Value;
                            displayName = match.Groups[3].Value;
                        }
                        else if (match.Groups.Count >= 3)
                        {
                            // LoosePropertyRegex 匹配
                            propertyName = match.Groups[1].Value;
                            displayName = match.Groups[2].Value;
                        }
                        
                        if (string.IsNullOrEmpty(propertyName))
                            continue;
                        
                        bool hasNonEnglish = NonEnglishRegex.IsMatch(displayName);
                        string newDisplayName = GenerateDisplayName(propertyName);
                        
                        var propInfo = new PropertyInfo
                        {
                            fullLine = line,
                            propertyName = propertyName,
                            originalDisplay = displayName,
                            newDisplay = hasNonEnglish ? newDisplayName : displayName,
                            lineNumber = i + 1,
                            hasNonEnglish = hasNonEnglish,
                            willBeFixed = hasNonEnglish
                        };
                        
                        analysis.properties.Add(propInfo);
                        
                        if (hasNonEnglish)
                        {
                            analysis.hasIssues = true;
                        }
                    }
                }
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[ShaderCleaner] 分析失败: {filePath}\n{e.Message}");
            return null;
        }
        
        return analysis;
    }

    private string GetRelativePath(string fullPath)
    {
        string relativePath = fullPath;
        string projectPath = Directory.GetCurrentDirectory();
        
        if (fullPath.StartsWith(projectPath))
        {
            relativePath = fullPath.Substring(projectPath.Length);
            if (relativePath.StartsWith("/") || relativePath.StartsWith("\\"))
            {
                relativePath = relativePath.Substring(1);
            }
        }
        
        return relativePath.Replace("\\", "/");
    }

    /// <summary>
    /// 从属性名生成友好的显示名称
    /// _MainTexture -> Main Texture
    /// _UseJizhi3 -> Use Jizhi 3
    /// </summary>
    private string GenerateDisplayName(string propertyName)
    {
        // 移除前导下划线
        string name = propertyName.TrimStart('_');
        
        // 在大写字母前添加空格（驼峰命名转换）
        string result = Regex.Replace(name, "([a-z])([A-Z])", "$1 $2");
        
        // 在数字前后添加空格
        result = Regex.Replace(result, "([a-zA-Z])([0-9])", "$1 $2");
        result = Regex.Replace(result, "([0-9])([a-zA-Z])", "$1 $2");
        
        // 处理连续大写（如 UV, ND）
        result = Regex.Replace(result, "([A-Z]+)([A-Z][a-z])", "$1 $2");
        
        return result;
    }
    
    #endregion

    #region 修复功能
    
    private void ApplySelectedFixes()
    {
        var selectedAnalysis = analysisResults
            .Where(a => a.isSelected && a.hasIssues && a.properties.Any(p => p.willBeFixed))
            .ToList();
            
        if (selectedAnalysis.Count == 0)
        {
            EditorUtility.DisplayDialog("提示", "没有选中需要修复的项目", "确定");
            return;
        }
        
        int totalFixes = selectedAnalysis.Sum(a => a.properties.Count(p => p.willBeFixed));
        
        if (!EditorUtility.DisplayDialog("确认修复", 
            $"将修复 {selectedAnalysis.Count} 个Shader文件中的 {totalFixes} 个属性\n\n" +
            "此操作不可撤销，建议先备份文件。", 
            "确认修复", "取消"))
        {
            return;
        }
        
        ApplyFixes(selectedAnalysis);
    }

    private void ApplyAllFixes()
    {
        var issueAnalysis = analysisResults.Where(a => a.hasIssues).ToList();
        
        if (issueAnalysis.Count == 0)
        {
            EditorUtility.DisplayDialog("提示", "没有需要修复的问题", "确定");
            return;
        }
        
        // 标记所有属性为需要修复
        foreach (var analysis in issueAnalysis)
        {
            analysis.isSelected = true;
            foreach (var prop in analysis.properties)
            {
                prop.willBeFixed = prop.hasNonEnglish;
            }
        }
        
        int totalFixes = issueAnalysis.Sum(a => a.properties.Count(p => p.willBeFixed));
        
        if (!EditorUtility.DisplayDialog("确认修复全部", 
            $"将修复 {issueAnalysis.Count} 个Shader文件中的 {totalFixes} 个属性\n\n" +
            "此操作不可撤销，建议先备份文件。", 
            "确认修复", "取消"))
        {
            return;
        }
        
        ApplyFixes(issueAnalysis);
    }

    private void ApplyFixes(List<ShaderAnalysis> analysisToFix)
    {
        int fixedFiles = 0;
        int fixedProps = 0;
        List<string> failedFiles = new List<string>();
        
        EditorUtility.DisplayProgressBar("修复Shader", "正在处理...", 0);
        
        try
        {
            for (int i = 0; i < analysisToFix.Count; i++)
            {
                var analysis = analysisToFix[i];
                EditorUtility.DisplayProgressBar("修复Shader", analysis.shaderName, 
                    (float)i / analysisToFix.Count);
                
                var propsToFix = analysis.properties.Where(p => p.willBeFixed && p.hasNonEnglish).ToList();
                
                if (propsToFix.Count > 0)
                {
                    if (FixShaderFile(analysis.shaderPath, propsToFix))
                    {
                        fixedFiles++;
                        fixedProps += propsToFix.Count;
                        
                        // 更新状态
                        foreach (var prop in propsToFix)
                        {
                            prop.originalDisplay = prop.newDisplay;
                            prop.hasNonEnglish = false;
                            prop.willBeFixed = false;
                        }
                        
                        analysis.hasIssues = analysis.properties.Any(p => p.hasNonEnglish);
                        analysis.isSelected = false;
                    }
                    else
                    {
                        failedFiles.Add(analysis.shaderPath);
                    }
                }
            }
        }
        finally
        {
            EditorUtility.ClearProgressBar();
        }
        
        AssetDatabase.Refresh();
        
        string message = $"已修复 {fixedFiles} 个文件中的 {fixedProps} 个属性";
        if (failedFiles.Count > 0)
        {
            message += $"\n\n失败 {failedFiles.Count} 个:\n" + string.Join("\n", failedFiles.Take(5));
            if (failedFiles.Count > 5)
            {
                message += $"\n... 等 {failedFiles.Count - 5} 个";
            }
        }
        
        EditorUtility.DisplayDialog("修复完成", message, "确定");
        
        // 重新计算统计
        totalIssuesFound = analysisResults.Sum(a => a.properties.Count(p => p.hasNonEnglish));
    }

    private bool FixShaderFile(string shaderPath, List<PropertyInfo> propsToFix)
    {
        try
        {
            string fullPath = Path.Combine(Directory.GetCurrentDirectory(), shaderPath);
            
            // 读取文件
            string content = File.ReadAllText(fullPath);
            string[] lines = File.ReadAllLines(fullPath);
            
            // 按行号创建查找表
            var fixLookup = propsToFix.ToDictionary(p => p.lineNumber - 1, p => p);
            
            bool modified = false;
            
            for (int i = 0; i < lines.Length; i++)
            {
                if (fixLookup.TryGetValue(i, out PropertyInfo prop))
                {
                    // 使用精确替换
                    string oldPattern = $"\"{prop.originalDisplay}\"";
                    string newPattern = $"\"{prop.newDisplay}\"";
                    
                    if (lines[i].Contains(oldPattern))
                    {
                        lines[i] = lines[i].Replace(oldPattern, newPattern);
                        modified = true;
                        Debug.Log($"  修复: {prop.propertyName} \"{prop.originalDisplay}\" → \"{prop.newDisplay}\"");
                    }
                }
            }
            
            if (modified)
            {
                File.WriteAllLines(fullPath, lines);
                Debug.Log($"[ShaderCleaner] 已保存: {shaderPath}");
            }
            
            return true;
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[ShaderCleaner] 修复失败: {shaderPath}\n{e.Message}");
            return false;
        }
    }
    
    #endregion

    #region 辅助功能
    
    private void ClearResults()
    {
        analysisResults.Clear();
        totalShadersScanned = 0;
        totalIssuesFound = 0;
    }
    
    private void PingShader(string shaderPath)
    {
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(shaderPath);
        if (shader != null)
        {
            EditorGUIUtility.PingObject(shader);
            Selection.activeObject = shader;
        }
    }
    
    private void OpenShaderFile(string shaderPath)
    {
        var asset = AssetDatabase.LoadAssetAtPath<Object>(shaderPath);
        if (asset != null)
        {
            AssetDatabase.OpenAsset(asset);
        }
    }
    
    private void ShowHelp()
    {
        EditorUtility.DisplayDialog("使用说明",
            "Shader属性清理工具 Pro\n\n" +
            "功能:\n" +
            "• 检测Shader属性中的非英文(中文等)显示名称\n" +
            "• 自动生成英文替换名称\n" +
            "• 支持批量修复\n\n" +
            "使用方法:\n" +
            "1. 拖拽Shader文件到手动列表，或设置扫描文件夹\n" +
            "2. 点击分析按钮进行检测\n" +
            "3. 预览并调整替换名称\n" +
            "4. 选择要修复的项目\n" +
            "5. 点击修复按钮应用更改\n\n" +
            "支持的属性格式:\n" +
            "• _Prop(\"显示名\", Type) = value\n" +
            "• [Attr]_Prop(\"显示名\", Type) = value\n" +
            "• [A][B][C]_Prop(\"显示名\", Type) = value",
            "知道了"
        );
    }
    
    private void ShowRegexTester()
    {
        RegexTesterWindow.ShowWindow();
    }
    
    #endregion
}

/// <summary>
/// 正则表达式测试窗口
/// </summary>
public class RegexTesterWindow : EditorWindow
{
    private string testInput = "[Enum(OFF,0,ON,1)][Space(5)][Header(___ND___)][Space(5)]_UseJizhi3(\"ND贴图极坐标\", Float) = 0";
    private string regexPattern = @"^\s*((?:\[[^\]]+\]\s*)*)(_?\w+)\s*\(\s*""([^""]*)""\s*,";
    private string result = "";
    private Vector2 scrollPos;
    
    public static void ShowWindow()
    {
        var window = GetWindow<RegexTesterWindow>("正则测试");
        window.minSize = new Vector2(500, 300);
    }
    
    private void OnGUI()
    {
        EditorGUILayout.LabelField("正则表达式测试工具", EditorStyles.boldLabel);
        EditorGUILayout.Space(10);
        
        EditorGUILayout.LabelField("测试输入:");
        testInput = EditorGUILayout.TextArea(testInput, GUILayout.Height(60));
        
        EditorGUILayout.Space(5);
        
        EditorGUILayout.LabelField("正则表达式:");
        regexPattern = EditorGUILayout.TextArea(regexPattern, GUILayout.Height(40));
        
        EditorGUILayout.Space(5);
        
        if (GUILayout.Button("测试匹配", GUILayout.Height(30)))
        {
            TestRegex();
        }
        
        EditorGUILayout.Space(10);
        
        EditorGUILayout.LabelField("匹配结果:");
        scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
        EditorGUILayout.TextArea(result, GUILayout.ExpandHeight(true));
        EditorGUILayout.EndScrollView();
    }
    
    private void TestRegex()
    {
        try
        {
            var regex = new Regex(regexPattern);
            var match = regex.Match(testInput);
            
            if (match.Success)
            {
                result = $"✓ 匹配成功!\n\n";
                result += $"完整匹配: \"{match.Value}\"\n\n";
                result += "各组内容:\n";
                
                for (int i = 0; i < match.Groups.Count; i++)
                {
                    result += $"  Group[{i}]: \"{match.Groups[i].Value}\"\n";
                }
                
                // 解析结果
                if (match.Groups.Count >= 4)
                {
                    result += $"\n解析结果:\n";
                    result += $"  属性标记: \"{match.Groups[1].Value.Trim()}\"\n";
                    result += $"  属性名: \"{match.Groups[2].Value}\"\n";
                    result += $"  显示名: \"{match.Groups[3].Value}\"\n";
                    
                    // 检测非英文
                    bool hasNonEnglish = Regex.IsMatch(match.Groups[3].Value, @"[^\x00-\x7F]");
                    result += $"  包含非英文: {hasNonEnglish}\n";
                }
            }
            else
            {
                result = "✗ 未匹配\n\n请检查正则表达式或输入内容";
            }
        }
        catch (System.Exception e)
        {
            result = $"✗ 正则表达式错误:\n{e.Message}";
        }
    }
}