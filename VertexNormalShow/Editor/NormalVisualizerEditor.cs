using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(NormalVisualizer))]
public class NormalVisualizerEditor : Editor
{
    private NormalVisualizer normalVisualizer;
    private SerializedProperty settingsProperty;
    
    private void OnEnable()
    {
        normalVisualizer = (NormalVisualizer)target;
        settingsProperty = serializedObject.FindProperty("settings");
    }
    
    public override void OnInspectorGUI()
    {
        serializedObject.Update();
        
        EditorGUILayout.LabelField("法线可视化工具", EditorStyles.boldLabel);
        EditorGUILayout.Space();
        
        // 显示设置
        EditorGUILayout.LabelField("显示设置", EditorStyles.boldLabel);
        EditorGUI.indentLevel++;
        
        var showNormals = settingsProperty.FindPropertyRelative("showNormals");
        EditorGUILayout.PropertyField(showNormals, new GUIContent("显示法线"));
        
        if (showNormals.boolValue)
        {
            var normalColor = settingsProperty.FindPropertyRelative("normalColor");
            EditorGUILayout.PropertyField(normalColor, new GUIContent("法线颜色"));
            
            var normalLength = settingsProperty.FindPropertyRelative("normalLength");
            EditorGUILayout.PropertyField(normalLength, new GUIContent("法线长度"));
            
            var displayRatio = settingsProperty.FindPropertyRelative("displayRatio");
            EditorGUILayout.PropertyField(displayRatio, new GUIContent("显示间隔", "每隔多少个顶点显示一条法线"));
        }
        
        EditorGUI.indentLevel--;
        EditorGUILayout.Space();
        
        // 过滤设置
        EditorGUILayout.LabelField("过滤设置", EditorStyles.boldLabel);
        EditorGUI.indentLevel++;
        
        var useLocalSpace = settingsProperty.FindPropertyRelative("useLocalSpace");
        EditorGUILayout.PropertyField(useLocalSpace, new GUIContent("使用本地坐标系"));
        
        var showOnlyVisible = settingsProperty.FindPropertyRelative("showOnlyVisible");
        EditorGUILayout.PropertyField(showOnlyVisible, new GUIContent("仅显示朝向摄像机的法线"));
        var showBakeMesh = settingsProperty.FindPropertyRelative("useBakedMesh");
        EditorGUILayout.PropertyField(showBakeMesh, new GUIContent("使用烘焙后的网格"));
        
        EditorGUI.indentLevel--;
        EditorGUILayout.Space();
        
        // 操作按钮
        EditorGUILayout.LabelField("操作", EditorStyles.boldLabel);
        
        GUILayout.BeginHorizontal();
        if (GUILayout.Button("刷新网格数据"))
        {
            normalVisualizer.RefreshMeshData();
            SceneView.RepaintAll();
        }
        
        if (GUILayout.Button("重新计算法线"))
        {
            RecalculateNormals();
        }
        GUILayout.EndHorizontal();
        
        // 信息显示
        ShowMeshInfo();
        
        serializedObject.ApplyModifiedProperties();
        
        if (GUI.changed)
        {
            SceneView.RepaintAll();
        }
    }
    
    private void RecalculateNormals()
    {
        var meshFilters = normalVisualizer.GetComponentsInChildren<MeshFilter>();
        foreach (var meshFilter in meshFilters)
        {
            if (meshFilter.sharedMesh != null)
            {
                Mesh mesh = meshFilter.sharedMesh;
                Undo.RecordObject(mesh, "Recalculate Normals");
                mesh.RecalculateNormals();
                EditorUtility.SetDirty(mesh);
            }
        }
        
        var skinnedRenderers = normalVisualizer.GetComponentsInChildren<SkinnedMeshRenderer>();
        foreach (var renderer in skinnedRenderers)
        {
            if (renderer.sharedMesh != null)
            {
                Mesh mesh = renderer.sharedMesh;
                Undo.RecordObject(mesh, "Recalculate Normals");
                mesh.RecalculateNormals();
                EditorUtility.SetDirty(mesh);
            }
        }
        
        AssetDatabase.SaveAssets();
        SceneView.RepaintAll();
    }
    
    private void ShowMeshInfo()
    {
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("网格信息", EditorStyles.boldLabel);
        
        var meshFilters = normalVisualizer.GetComponentsInChildren<MeshFilter>();
        var skinnedRenderers = normalVisualizer.GetComponentsInChildren<SkinnedMeshRenderer>();
        
        int totalVertices = 0;
        int meshCount = 0;
        
        foreach (var meshFilter in meshFilters)
        {
            if (meshFilter.sharedMesh != null)
            {
                totalVertices += meshFilter.sharedMesh.vertexCount;
                meshCount++;
            }
        }
        
        foreach (var renderer in skinnedRenderers)
        {
            if (renderer.sharedMesh != null)
            {
                totalVertices += renderer.sharedMesh.vertexCount;
                meshCount++;
            }
        }
        
        EditorGUILayout.LabelField($"网格数量: {meshCount}");
        EditorGUILayout.LabelField($"总顶点数: {totalVertices}");
        
        if (normalVisualizer.settings.showNormals)
        {
            int displayedNormals = Mathf.CeilToInt(totalVertices / (float)normalVisualizer.settings.displayRatio);
            EditorGUILayout.LabelField($"显示的法线数: {displayedNormals}");
        }
    }
}

