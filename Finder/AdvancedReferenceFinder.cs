using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

public class AdvancedReferenceFinder : EditorWindow
{
    private Object targetObject;
    private Vector2 scrollPosition;
    private List<ReferenceResult> results = new List<ReferenceResult>();
    
    // 搜索选项
    private bool searchInScene = true;
    private bool searchInPrefabs = false;
    private bool searchInactiveObjects = true;
    private bool showComponentDetails = true;
    
    // 过滤选项
    private string componentFilter = "";
    private List<ReferenceResult> filteredResults = new List<ReferenceResult>();

    private class ReferenceResult
    {
        public GameObject gameObject;
        public Component component;
        public string propertyPath;
        public string componentType;
        public string hierarchyPath;
    }

    [MenuItem("Tools/TempByAI/Finder/高级引用查找器 %#r")]
    public static void ShowWindow()
    {
        var window = GetWindow<AdvancedReferenceFinder>("高级引用查找器");
        window.minSize = new Vector2(500, 400);
    }

    private void OnSelectionChange()
    {
        Repaint();
    }

    private void OnGUI()
    {
        DrawHeader();
        DrawTargetSelection();
        DrawSearchOptions();
        DrawSearchButtons();
        DrawFilter();
        DrawResults();
        DrawFooter();
    }

    private void DrawHeader()
    {
        EditorGUILayout.Space(10);
        GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
        {
            fontSize = 18,
            alignment = TextAnchor.MiddleCenter
        };
        EditorGUILayout.LabelField("🔍 高级场景引用查找器", titleStyle);
        EditorGUILayout.Space(5);
    }

    private void DrawTargetSelection()
    {
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        
        EditorGUILayout.LabelField("目标对象", EditorStyles.boldLabel);
        
        EditorGUILayout.BeginHorizontal();
        targetObject = EditorGUILayout.ObjectField("查找目标:", targetObject, typeof(Object), true);
        
        if (GUILayout.Button("使用选中", GUILayout.Width(80)))
        {
            targetObject = Selection.activeObject;
        }
        EditorGUILayout.EndHorizontal();

        if (targetObject != null)
        {
            EditorGUILayout.LabelField($"类型: {targetObject.GetType().Name}", EditorStyles.miniLabel);
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawSearchOptions()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        
        EditorGUILayout.LabelField("搜索选项", EditorStyles.boldLabel);
        
        EditorGUILayout.BeginHorizontal();
        searchInScene = EditorGUILayout.ToggleLeft("场景对象", searchInScene, GUILayout.Width(100));
        searchInactiveObjects = EditorGUILayout.ToggleLeft("包含未激活", searchInactiveObjects, GUILayout.Width(100));
        showComponentDetails = EditorGUILayout.ToggleLeft("显示详情", showComponentDetails);
        EditorGUILayout.EndHorizontal();
        
        EditorGUILayout.EndVertical();
    }

    private void DrawSearchButtons()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginHorizontal();
        
        GUI.enabled = targetObject != null;
        
        GUI.backgroundColor = new Color(0.5f, 0.8f, 0.5f);
        if (GUILayout.Button("🔍 开始搜索", GUILayout.Height(35)))
        {
            FindReferences();
        }
        GUI.backgroundColor = Color.white;
        
        GUI.backgroundColor = new Color(0.8f, 0.8f, 0.5f);
        if (GUILayout.Button("🔍 搜索反向引用", GUILayout.Height(35)))
        {
            FindReverseReferences();
        }
        GUI.backgroundColor = Color.white;
        
        if (GUILayout.Button("清除结果", GUILayout.Height(35), GUILayout.Width(80)))
        {
            results.Clear();
            filteredResults.Clear();
        }
        
        GUI.enabled = true;
        
        EditorGUILayout.EndHorizontal();
    }

    private void DrawFilter()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField("过滤组件:", GUILayout.Width(70));
        string newFilter = EditorGUILayout.TextField(componentFilter);
        if (newFilter != componentFilter)
        {
            componentFilter = newFilter;
            ApplyFilter();
        }
        EditorGUILayout.EndHorizontal();
    }

    private void DrawResults()
    {
        EditorGUILayout.Space(5);
        
        var displayResults = string.IsNullOrEmpty(componentFilter) ? results : filteredResults;
        
        EditorGUILayout.LabelField($"搜索结果: {displayResults.Count} 个引用", EditorStyles.boldLabel);
        
        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);
        
        if (displayResults.Count > 0)
        {
            // 按GameObject分组显示
            var groupedResults = displayResults.GroupBy(r => r.gameObject);
            
            foreach (var group in groupedResults)
            {
                DrawGroupedResult(group.Key, group.ToList());
            }
        }
        else if (targetObject != null)
        {
            EditorGUILayout.HelpBox("没有找到引用，点击搜索按钮开始搜索。", MessageType.Info);
        }
        else
        {
            EditorGUILayout.HelpBox("请先选择一个目标对象。", MessageType.Warning);
        }
        
        EditorGUILayout.EndScrollView();
    }

    private void DrawGroupedResult(GameObject go, List<ReferenceResult> groupResults)
    {
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
        
        // 游戏对象行
        EditorGUILayout.BeginHorizontal();
        
        // 折叠箭头和对象名
        EditorGUILayout.ObjectField(go, typeof(GameObject), true, GUILayout.Width(250));
        
        GUILayout.FlexibleSpace();
        
        EditorGUILayout.LabelField($"({groupResults.Count}个引用)", GUILayout.Width(80));
        
        if (GUILayout.Button("定位", GUILayout.Width(50)))
        {
            Selection.activeGameObject = go;
            EditorGUIUtility.PingObject(go);
            SceneView.lastActiveSceneView?.FrameSelected();
        }
        
        EditorGUILayout.EndHorizontal();
        
        // 显示层级路径
        if (groupResults.Count > 0)
        {
            EditorGUILayout.LabelField($"   路径: {groupResults[0].hierarchyPath}", EditorStyles.miniLabel);
        }
        
        // 详细信息
        if (showComponentDetails)
        {
            EditorGUI.indentLevel++;
            foreach (var result in groupResults)
            {
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField($"• [{result.componentType}]", GUILayout.Width(150));
                EditorGUILayout.LabelField($"→ {result.propertyPath}");
                
                if (GUILayout.Button("选中", GUILayout.Width(40)))
                {
                    Selection.activeObject = result.component;
                }
                EditorGUILayout.EndHorizontal();
            }
            EditorGUI.indentLevel--;
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawFooter()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginHorizontal();
        
        if (GUILayout.Button("导出结果"))
        {
            ExportResults();
        }
        
        if (GUILayout.Button("全选引用对象"))
        {
            SelectAllReferencingObjects();
        }
        
        EditorGUILayout.EndHorizontal();
    }

    private void FindReferences()
    {
        if (targetObject == null) return;

        results.Clear();
        
        GameObject[] allObjects = UnityEngine.SceneManagement.SceneManager
            .GetActiveScene().GetRootGameObjects();

        int totalChecked = 0;

        foreach (GameObject root in allObjects)
        {
            Transform[] allTransforms = root.GetComponentsInChildren<Transform>(searchInactiveObjects);
            
            foreach (Transform t in allTransforms)
            {
                GameObject go = t.gameObject;
                if (go == targetObject) continue;
                
                Component[] components = go.GetComponents<Component>();
                foreach (Component component in components)
                {
                    if (component == null || component == targetObject) continue;
                    
                    CheckComponentForReferences(component, go);
                    totalChecked++;
                }
            }
        }

        ApplyFilter();
        Debug.Log($"[引用查找器] 检查了 {totalChecked} 个组件，找到 {results.Count} 个引用");
    }

    // 反向引用：查找目标对象引用了哪些其他对象
    private void FindReverseReferences()
    {
        if (targetObject == null) return;

        results.Clear();

        GameObject targetGO = null;
        
        if (targetObject is GameObject go)
        {
            targetGO = go;
        }
        else if (targetObject is Component comp)
        {
            targetGO = comp.gameObject;
        }

        if (targetGO == null)
        {
            Debug.LogWarning("目标必须是GameObject或Component");
            return;
        }

        Component[] components = targetGO.GetComponents<Component>();
        
        foreach (Component component in components)
        {
            if (component == null) continue;
            
            SerializedObject serializedObject = new SerializedObject(component);
            SerializedProperty property = serializedObject.GetIterator();

            while (property.NextVisible(true))
            {
                if (property.propertyType == SerializedPropertyType.ObjectReference)
                {
                    Object refObj = property.objectReferenceValue;
                    if (refObj != null && refObj != targetObject)
                    {
                        GameObject refGO = null;
                        
                        if (refObj is GameObject g)
                            refGO = g;
                        else if (refObj is Component c)
                            refGO = c.gameObject;

                        if (refGO != null)
                        {
                            results.Add(new ReferenceResult
                            {
                                gameObject = refGO,
                                component = component,
                                propertyPath = property.propertyPath,
                                componentType = component.GetType().Name,
                                hierarchyPath = GetHierarchyPath(refGO)
                            });
                        }
                    }
                }
            }
            
            serializedObject.Dispose();
        }

        ApplyFilter();
        Debug.Log($"[引用查找器] 目标对象引用了 {results.Count} 个其他对象");
    }

    private void CheckComponentForReferences(Component component, GameObject go)
    {
        SerializedObject serializedObject = new SerializedObject(component);
        SerializedProperty property = serializedObject.GetIterator();

        while (property.NextVisible(true))
        {
            if (property.propertyType == SerializedPropertyType.ObjectReference)
            {
                if (property.objectReferenceValue == targetObject)
                {
                    results.Add(new ReferenceResult
                    {
                        gameObject = go,
                        component = component,
                        propertyPath = property.propertyPath,
                        componentType = component.GetType().Name,
                        hierarchyPath = GetHierarchyPath(go)
                    });
                }
            }
        }

        serializedObject.Dispose();
    }

    private string GetHierarchyPath(GameObject go)
    {
        string path = go.name;
        Transform parent = go.transform.parent;
        
        while (parent != null)
        {
            path = parent.name + "/" + path;
            parent = parent.parent;
        }
        
        return path;
    }

    private void ApplyFilter()
    {
        if (string.IsNullOrEmpty(componentFilter))
        {
            filteredResults = results;
        }
        else
        {
            filteredResults = results
                .Where(r => r.componentType.ToLower().Contains(componentFilter.ToLower()) ||
                           r.gameObject.name.ToLower().Contains(componentFilter.ToLower()))
                .ToList();
        }
    }

    private void SelectAllReferencingObjects()
    {
        var displayResults = string.IsNullOrEmpty(componentFilter) ? results : filteredResults;
        Selection.objects = displayResults.Select(r => r.gameObject).Distinct().ToArray();
    }

    private void ExportResults()
    {
        var displayResults = string.IsNullOrEmpty(componentFilter) ? results : filteredResults;
        
        System.Text.StringBuilder sb = new System.Text.StringBuilder();
        sb.AppendLine($"引用查找结果 - 目标: {targetObject?.name}");
        sb.AppendLine($"时间: {System.DateTime.Now}");
        sb.AppendLine("========================================");
        
        foreach (var result in displayResults)
        {
            sb.AppendLine($"对象: {result.gameObject.name}");
            sb.AppendLine($"  路径: {result.hierarchyPath}");
            sb.AppendLine($"  组件: {result.componentType}");
            sb.AppendLine($"  属性: {result.propertyPath}");
            sb.AppendLine();
        }

        string path = EditorUtility.SaveFilePanel("保存结果", "", "ReferenceResults", "txt");
        if (!string.IsNullOrEmpty(path))
        {
            System.IO.File.WriteAllText(path, sb.ToString());
            Debug.Log($"结果已导出到: {path}");
        }
    }
}
