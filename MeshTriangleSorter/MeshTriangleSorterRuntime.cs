using UnityEngine;
using System.Collections.Generic;

[System.Serializable]
public class MeshTriangleSorterRuntime : MonoBehaviour
{
    [Header("Sorting Settings")]
    public bool useVertexColor = true;
    public bool useBlueChannel = true;
    public bool reverseOrder = false;
    public bool sortOnStart = false;
    
    private Mesh originalMesh;
    private MeshRenderer meshRenderer;
    private SkinnedMeshRenderer skinnedMeshRenderer;
    private MeshFilter meshFilter;
    
    void Start()
    {
        Initialize();
        
        if (sortOnStart)
        {
            SortTriangles();
        }
    }
    
    void Initialize()
    {
        meshRenderer = GetComponent<MeshRenderer>();
        skinnedMeshRenderer = GetComponent<SkinnedMeshRenderer>();
        meshFilter = GetComponent<MeshFilter>();
        
        // 保存原始mesh引用
        if (skinnedMeshRenderer != null)
        {
            originalMesh = skinnedMeshRenderer.sharedMesh;
        }
        else if (meshFilter != null)
        {
            originalMesh = meshFilter.sharedMesh;
        }
    }
    
    [ContextMenu("Sort Triangles")]
    public void SortTriangles()
    {
        if (originalMesh == null)
        {
            Debug.LogError("No mesh found to sort");
            return;
        }
        
        Mesh sortedMesh = CreateSortedMesh(originalMesh);
        
        if (sortedMesh != null)
        {
            if (skinnedMeshRenderer != null)
            {
                skinnedMeshRenderer.sharedMesh = sortedMesh;
            }
            else if (meshFilter != null)
            {
                meshFilter.sharedMesh = sortedMesh;
            }
        }
    }
    
    [ContextMenu("Reset to Original")]
    public void ResetToOriginal()
    {
        if (originalMesh == null) return;
        
        if (skinnedMeshRenderer != null)
        {
            skinnedMeshRenderer.sharedMesh = originalMesh;
        }
        else if (meshFilter != null)
        {
            meshFilter.sharedMesh = originalMesh;
        }
    }
    
    Mesh CreateSortedMesh(Mesh sourceMesh)
    {
        Mesh newMesh = Instantiate(sourceMesh);
        newMesh.name = sourceMesh.name + "_RuntimeSorted";
        
        Vector3[] vertices = newMesh.vertices;
        Color[] colors = newMesh.colors;
        
        for (int submeshIndex = 0; submeshIndex < newMesh.subMeshCount; submeshIndex++)
        {
            int[] triangles = newMesh.GetTriangles(submeshIndex);
            List<TriangleData> triangleDataList = new List<TriangleData>();
            
            for (int i = 0; i < triangles.Length; i += 3)
            {
                TriangleData triangleData = new TriangleData();
                triangleData.indices = new int[] { triangles[i], triangles[i + 1], triangles[i + 2] };
                triangleData.sortValue = CalculateTriangleSortValue(triangleData.indices, vertices, colors);
                triangleDataList.Add(triangleData);
            }
            
            if (reverseOrder)
            {
                triangleDataList.Sort((a, b) => b.sortValue.CompareTo(a.sortValue));
            }
            else
            {
                triangleDataList.Sort((a, b) => a.sortValue.CompareTo(b.sortValue));
            }
            
            int[] sortedTriangles = new int[triangles.Length];
            for (int i = 0; i < triangleDataList.Count; i++)
            {
                sortedTriangles[i * 3] = triangleDataList[i].indices[0];
                sortedTriangles[i * 3 + 1] = triangleDataList[i].indices[1];
                sortedTriangles[i * 3 + 2] = triangleDataList[i].indices[2];
            }
            
            newMesh.SetTriangles(sortedTriangles, submeshIndex);
        }
        
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
                if (useBlueChannel)
                {
                    totalValue += colors[vertexIndex].b;
                }
                else
                {
                    Color color = colors[vertexIndex];
                    totalValue += (color.r + color.g + color.b) / 3f;
                }
            }
            else
            {
                totalValue += vertices[vertexIndex].y;
            }
        }
        
        return totalValue / 3f;
    }
}
