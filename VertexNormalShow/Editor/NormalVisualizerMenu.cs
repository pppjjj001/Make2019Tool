using UnityEngine;
using UnityEditor;

public static class NormalVisualizerMenu
{
    [MenuItem("GameObject/3D Object/Add Normal Visualizer", false, 10)]
    public static void AddNormalVisualizer()
    {
        GameObject[] selectedObjects = Selection.gameObjects;
        
        if (selectedObjects.Length == 0)
        {
            EditorUtility.DisplayDialog("错误", "请先选择一个GameObject", "确定");
            return;
        }
        
        foreach (GameObject obj in selectedObjects)
        {
            if (obj.GetComponent<NormalVisualizer>() == null)
            {
                Undo.AddComponent<NormalVisualizer>(obj);
                EditorUtility.SetDirty(obj);
            }
        }
        
        SceneView.RepaintAll();
    }
    
    [MenuItem("GameObject/3D Object/Add Normal Visualizer", true)]
    public static bool ValidateAddNormalVisualizer()
    {
        return Selection.activeGameObject != null;
    }
    
    [MenuItem("Tools/Normal Visualizer/Add to All MeshRenderers in Scene")]
    public static void AddToAllMeshRenderersInScene()
    {
        MeshRenderer[] meshRenderers = Object.FindObjectsOfType<MeshRenderer>();
        int addedCount = 0;
        
        foreach (MeshRenderer renderer in meshRenderers)
        {
            if (renderer.GetComponent<NormalVisualizer>() == null)
            {
                Undo.AddComponent<NormalVisualizer>(renderer.gameObject);
                addedCount++;
            }
        }
        
        EditorUtility.DisplayDialog("完成", $"已为 {addedCount} 个对象添加法线可视化器", "确定");
        SceneView.RepaintAll();
    }
    
    [MenuItem("Tools/Normal Visualizer/Remove All in Scene")]
    public static void RemoveAllInScene()
    {
        NormalVisualizer[] visualizers = Object.FindObjectsOfType<NormalVisualizer>();
        
        foreach (NormalVisualizer visualizer in visualizers)
        {
            Undo.DestroyObjectImmediate(visualizer);
        }
        
        EditorUtility.DisplayDialog("完成", $"已移除 {visualizers.Length} 个法线可视化器", "确定");
        SceneView.RepaintAll();
    }
}

