using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

public class MeshTriangleSorter : EditorWindow
{
    private GameObject targetObject;
    private bool useVertexColor = true;
    private bool useBlueChannel = true;
    private bool reverseOrder = false;
    
    [MenuItem("Tools/TempByAI/Mesh Triangle Sorter")]
    public static void ShowWindow()
    {
        GetWindow<MeshTriangleSorter>("Mesh Triangle Sorter");
    }
    
    void OnGUI()
    {
        GUILayout.Label("Mesh Triangle Sorting Tool", EditorStyles.boldLabel);
        
        targetObject = (GameObject)EditorGUILayout.ObjectField("Target Object", targetObject, typeof(GameObject), true);
        
        useVertexColor = EditorGUILayout.Toggle("Use Vertex Color", useVertexColor);
        
        if (useVertexColor)
        {
            useBlueChannel = EditorGUILayout.Toggle("Use Blue Channel", useBlueChannel);
        }
        
        reverseOrder = EditorGUILayout.Toggle("Reverse Order (Large First)", reverseOrder);
        
        EditorGUILayout.Space();
        
        if (GUILayout.Button("Sort Triangles"))
        {
            SortMeshTriangles();
        }
        
        if (GUILayout.Button("Reset to Original"))
        {
            ResetMeshTriangles();
        }
    }
    
    void SortMeshTriangles()
    {
        if (targetObject == null)
        {
            EditorUtility.DisplayDialog("Error", "Please select a target object", "OK");
            return;
        }
        
        // 检查是否有MeshRenderer或SkinnedMeshRenderer
        MeshRenderer meshRenderer = targetObject.GetComponent<MeshRenderer>();
        SkinnedMeshRenderer skinnedMeshRenderer = targetObject.GetComponent<SkinnedMeshRenderer>();
        
        if (meshRenderer == null && skinnedMeshRenderer == null)
        {
            EditorUtility.DisplayDialog("Error", "Target object must have MeshRenderer or SkinnedMeshRenderer", "OK");
            return;
        }
        
        Mesh mesh = null;
        bool isSkinnedMesh = false;
        
        if (skinnedMeshRenderer != null)
        {
            mesh = skinnedMeshRenderer.sharedMesh;
            isSkinnedMesh = true;
        }
        else if (meshRenderer != null)
        {
            MeshFilter meshFilter = targetObject.GetComponent<MeshFilter>();
            if (meshFilter != null)
            {
                mesh = meshFilter.sharedMesh;
            }
        }
        
        if (mesh == null)
        {
            EditorUtility.DisplayDialog("Error", "No mesh found on target object", "OK");
            return;
        }
        
        // 创建mesh副本
        Mesh newMesh = CreateSortedMesh(mesh);
        
        if (newMesh != null)
        {
            // 保存原始mesh的引用
            if (!newMesh.name.Contains("_Original"))
            {
                string assetPath = AssetDatabase.GetAssetPath(mesh);
                if (!string.IsNullOrEmpty(assetPath))
                {
                    // 如果是资源文件，创建备份
                    Mesh backupMesh = Object.Instantiate(mesh);
                    backupMesh.name = mesh.name + "_Original";
                    AssetDatabase.CreateAsset(backupMesh, assetPath.Replace(".asset", "_Original.asset"));
                }
            }
            
            // 应用新的mesh
            if (isSkinnedMesh)
            {
                skinnedMeshRenderer.sharedMesh = newMesh;
            }
            else
            {
                targetObject.GetComponent<MeshFilter>().sharedMesh = newMesh;
            }
            
            // 保存新mesh
            string savePath = EditorUtility.SaveFilePanelInProject(
                "Save Sorted Mesh", 
                mesh.name + "_Sorted", 
                "asset", 
                "Save sorted mesh");
                
            if (!string.IsNullOrEmpty(savePath))
            {
                AssetDatabase.CreateAsset(newMesh, savePath);
                AssetDatabase.SaveAssets();
            }
            
            Debug.Log("Mesh triangles sorted successfully!");
        }
    }
    
    Mesh CreateSortedMesh(Mesh originalMesh)
    {
        Mesh newMesh = Object.Instantiate(originalMesh);
        newMesh.name = originalMesh.name + "_Sorted";
        
        Vector3[] vertices = newMesh.vertices;
        Color[] colors = newMesh.colors;
        Vector3[] normals = newMesh.normals;
        Vector2[] uv = newMesh.uv;
        Vector2[] uv2 = newMesh.uv2;
        Vector4[] tangents = newMesh.tangents;
        BoneWeight[] boneWeights = newMesh.boneWeights;
        
        // 处理每个子网格
        for (int submeshIndex = 0; submeshIndex < newMesh.subMeshCount; submeshIndex++)
        {
            int[] triangles = newMesh.GetTriangles(submeshIndex);
            
            // 创建三角形数据列表
            List<TriangleData> triangleDataList = new List<TriangleData>();
            
            for (int i = 0; i < triangles.Length; i += 3)
            {
                TriangleData triangleData = new TriangleData();
                triangleData.indices = new int[] { triangles[i], triangles[i + 1], triangles[i + 2] };
                
                // 计算三角形的排序值
                triangleData.sortValue = CalculateTriangleSortValue(triangleData.indices, vertices, colors);
                
                triangleDataList.Add(triangleData);
            }
            
            // 排序三角形
            if (reverseOrder)
            {
                triangleDataList.Sort((a, b) => b.sortValue.CompareTo(a.sortValue));
            }
            else
            {
                triangleDataList.Sort((a, b) => a.sortValue.CompareTo(b.sortValue));
            }
            
            // 重新组装三角形数组
            int[] sortedTriangles = new int[triangles.Length];
            for (int i = 0; i < triangleDataList.Count; i++)
            {
                sortedTriangles[i * 3] = triangleDataList[i].indices[0];
                sortedTriangles[i * 3 + 1] = triangleDataList[i].indices[1];
                sortedTriangles[i * 3 + 2] = triangleDataList[i].indices[2];
            }
            
            newMesh.SetTriangles(sortedTriangles, submeshIndex);
        }
        
        // 重新计算bounds
        newMesh.RecalculateBounds();
        
        return newMesh;
    }
    
    float CalculateTriangleSortValue(int[] indices, Vector3[] vertices, Color[] colors)
    {
        float totalValue = 0f;
        
        for (int i = 0; i < 3; i++)
        {
            int vertexIndex = indices[i];
            
            if (useVertexColor && colors != null && colors.Length > vertexIndex)
            {
                // 使用顶点颜色
                if (useBlueChannel)
                {
                    totalValue += colors[vertexIndex].b;
                }
                else
                {
                    // 使用颜色的亮度
                    Color color = colors[vertexIndex];
                    totalValue += (color.r + color.g + color.b) / 3f;
                }
            }
            else
            {
                // 如果没有顶点颜色，使用Y坐标作为替代
                totalValue += vertices[vertexIndex].y;
            }
        }
        
        // 返回三角形的平均值
        return totalValue / 3f;
    }
    
    void ResetMeshTriangles()
    {
        if (targetObject == null) return;
        
        // 查找原始mesh
        string[] guids = AssetDatabase.FindAssets("t:Mesh");
        
        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            Mesh mesh = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            
            if (mesh != null && mesh.name.Contains("_Original"))
            {
                string originalName = mesh.name.Replace("_Original", "");
                
                // 检查是否匹配当前对象的mesh
                MeshRenderer meshRenderer = targetObject.GetComponent<MeshRenderer>();
                SkinnedMeshRenderer skinnedMeshRenderer = targetObject.GetComponent<SkinnedMeshRenderer>();
                
                if (skinnedMeshRenderer != null && skinnedMeshRenderer.sharedMesh.name.Contains(originalName))
                {
                    skinnedMeshRenderer.sharedMesh = mesh;
                    Debug.Log("Skinned mesh reset to original");
                    return;
                }
                else if (meshRenderer != null)
                {
                    MeshFilter meshFilter = targetObject.GetComponent<MeshFilter>();
                    if (meshFilter != null && meshFilter.sharedMesh.name.Contains(originalName))
                    {
                        meshFilter.sharedMesh = mesh;
                        Debug.Log("Mesh reset to original");
                        return;
                    }
                }
            }
        }
        
        Debug.LogWarning("Original mesh not found");
    }
}
