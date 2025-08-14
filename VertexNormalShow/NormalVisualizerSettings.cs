using UnityEngine;

[System.Serializable]
public class NormalVisualizerSettings
{
    [Header("显示设置")]
    public bool showNormals = true;
    public Color normalColor = Color.cyan;
    public float normalLength = 0.1f;
    
    [Header("过滤设置")]
    [Range(1, 100)]
    public int displayRatio = 10; // 显示比例，1表示显示所有法线
    
    [Header("渲染设置")]
    public bool useLocalSpace = true; // 是否使用本地坐标系
    public bool showOnlyVisible = false; // 是否只显示朝向摄像机的法线
    
    [Header("SkinnedMesh设置")]
    public bool useBakedMesh = true; // 是否使用烘焙后的网格（跟随动画）

    public bool useCustomBake = true;
}

public class NormalVisualizer : MonoBehaviour
{
    public NormalVisualizerSettings settings = new NormalVisualizerSettings();
    
    private Mesh[] meshes;
    private MeshFilter[] meshFilters;
    private SkinnedMeshRenderer[] skinnedMeshRenderers;
    
    // 用于存储烘焙后的网格数据
    private Mesh[] bakedMeshes;
    private BakeDataCustom[] bakeDatas;
    private void OnValidate()
    {
        RefreshMeshData();
    }
    
    public void RefreshMeshData()
    {
        // 获取所有相关的网格组件
        meshFilters = GetComponentsInChildren<MeshFilter>();
        skinnedMeshRenderers = GetComponentsInChildren<SkinnedMeshRenderer>();
        // 为每个 SkinnedMeshRenderer 创建烘焙网格
        if (skinnedMeshRenderers != null && skinnedMeshRenderers.Length > 0)
        {
            bakedMeshes = new Mesh[skinnedMeshRenderers.Length];
            bakeDatas = new BakeDataCustom[skinnedMeshRenderers.Length];
            for (int i = 0; i < skinnedMeshRenderers.Length; i++)
            {
                bakedMeshes[i] = new Mesh();
                bakeDatas[i] = new BakeDataCustom();
                bakeDatas[i].target = skinnedMeshRenderers[i];
                bakeDatas[i].ExtractBindPose();
            }
        }
    }
    private void OnDestroy()
    {
        // 清理烘焙的网格
        if (bakedMeshes != null)
        {
            for (int i = 0; i < bakedMeshes.Length; i++)
            {
                if (bakedMeshes[i] != null)
                {
                    DestroyImmediate(bakedMeshes[i]);
                }
            }
        }
    }
    
    private void OnDrawGizmos()
    {
        if (!settings.showNormals) return;
        
        DrawNormals();
    }
    
    private void DrawNormals()
    {
        Gizmos.color = settings.normalColor;
        
        // 处理 MeshFilter 组件
        if (meshFilters != null)
        {
            foreach (var meshFilter in meshFilters)
            {
                if (meshFilter.sharedMesh != null)
                {
                    DrawMeshNormals(meshFilter.sharedMesh, meshFilter.transform);
                }
            }
        }
        // 处理 SkinnedMeshRenderer 组件
        if (skinnedMeshRenderers != null && bakedMeshes != null)
        {
            for (int i = 0; i < skinnedMeshRenderers.Length; i++)
            {
                var skinnedRenderer = skinnedMeshRenderers[i];
                if (skinnedRenderer != null && skinnedRenderer.sharedMesh != null)
                {
                    if (settings.useBakedMesh)
                    {
                        // 烘焙当前帧的网格数据（包含动画变形）
                        if (settings.useCustomBake)
                        {
                            Vector3[] poseVerts;
                            Vector3[] poseNormals;
                            Vector4[] poseTangents;
                            bakeDatas[i].BakeOnCurrentPose(out poseVerts, out poseNormals, out poseTangents);
                            DrawMeshNormals(poseVerts, poseNormals,skinnedRenderer.transform);
                        }
                        else
                        {
                            skinnedRenderer.BakeMesh(bakedMeshes[i]);
                            DrawMeshNormals(bakedMeshes[i], skinnedRenderer.transform, true);
                        }
                    }
                    else
                    {
                        // 使用原始网格数据（不跟随动画）
                        DrawMeshNormals(skinnedRenderer.sharedMesh, skinnedRenderer.transform,false);
                    }
                }
            }
        }
        // // 处理 SkinnedMeshRenderer 组件
        // if (skinnedMeshRenderers != null)
        // {
        //     foreach (var skinnedRenderer in skinnedMeshRenderers)
        //     {
        //         
        //         if (skinnedRenderer.sharedMesh != null)
        //         {
        //             skinnedRenderer.BakeMesh(bakedMeshes[i]);
        //             DrawMeshNormals(skinnedRenderer.sharedMesh, skinnedRenderer.transform);
        //         }
        //     }
        // }
    }
    
    private void DrawMeshNormals(Vector3[] vertices,Vector3[] normals, Transform meshTransform)
    {
        if (vertices == null || normals == null || vertices.Length != normals.Length)
            return;
        
        for (int i = 0; i < vertices.Length; i += settings.displayRatio)
        {
            Vector3 worldVertex, worldNormal;
            
            if (settings.useLocalSpace)
            {
                // 使用本地坐标系
                worldVertex = vertices[i];
                worldNormal = meshTransform.TransformDirection(normals[i]).normalized;
            }
            else
            {
                // 使用世界坐标系
                worldVertex = vertices[i];
                worldNormal = normals[i].normalized;
            }
            
            // 可选：只显示朝向摄像机的法线
            if (settings.showOnlyVisible)
            {
                Camera sceneCamera = Camera.current;
                if (sceneCamera != null)
                {
                    Vector3 toCameraDirection = (sceneCamera.transform.position - worldVertex).normalized;
                    if (Vector3.Dot(worldNormal, toCameraDirection) <= 0)
                        continue;
                }
            }
            
            // 绘制法线
            Vector3 normalEnd = worldVertex + worldNormal * settings.normalLength;
            Gizmos.DrawLine(worldVertex, normalEnd);
            
            // 绘制法线箭头
            DrawArrowHead(worldVertex, normalEnd, settings.normalLength * 0.2f);
        }
    }
    private void DrawMeshNormals(Mesh mesh, Transform meshTransform)
    {
        Vector3[] vertices = mesh.vertices;
        Vector3[] normals = mesh.normals;
        
        if (vertices == null || normals == null || vertices.Length != normals.Length)
            return;
        
        for (int i = 0; i < vertices.Length; i += settings.displayRatio)
        {
            Vector3 worldVertex, worldNormal;
            
            if (settings.useLocalSpace)
            {
                // 使用本地坐标系
                worldVertex = meshTransform.TransformPoint(vertices[i]);
                worldNormal = meshTransform.TransformDirection(normals[i]).normalized;
            }
            else
            {
                // 使用世界坐标系
                worldVertex = vertices[i];
                worldNormal = normals[i];
            }
            
            // 可选：只显示朝向摄像机的法线
            if (settings.showOnlyVisible)
            {
                Camera sceneCamera = Camera.current;
                if (sceneCamera != null)
                {
                    Vector3 toCameraDirection = (sceneCamera.transform.position - worldVertex).normalized;
                    if (Vector3.Dot(worldNormal, toCameraDirection) <= 0)
                        continue;
                }
            }
            
            // 绘制法线
            Vector3 normalEnd = worldVertex + worldNormal * settings.normalLength;
            Gizmos.DrawLine(worldVertex, normalEnd);
            
            // 绘制法线箭头
            DrawArrowHead(worldVertex, normalEnd, settings.normalLength * 0.2f);
        }
    }
    private void DrawMeshNormals(Mesh mesh, Transform meshTransform, bool isSkinnedMesh)
    {
        Vector3[] vertices = mesh.vertices;
        Vector3[] normals = mesh.normals;
        
        if (vertices == null || normals == null || vertices.Length != normals.Length)
            return;
        
        // 如果法线数组为空，尝试重新计算
        if (normals.Length == 0)
        {
            mesh.RecalculateNormals();
            normals = mesh.normals;
        }
        
        for (int i = 0; i < vertices.Length; i += settings.displayRatio)
        {
            Vector3 worldVertex, worldNormal;
            
            if (isSkinnedMesh && settings.useBakedMesh)
            {
                // 对于烘焙后的SkinnedMesh，顶点和法线已经在世界空间中
                if (settings.useLocalSpace)
                {
                    worldVertex = meshTransform.TransformPoint(vertices[i]);//meshTransform.TransformPoint(vertices[i]);
                    worldNormal = meshTransform.InverseTransformDirection(normals[i]).normalized;
                }
                else
                {
                    worldVertex = vertices[i];
                    //worldVertex = meshTransform.TransformPoint(vertices[i]);
                    worldNormal = normals[i].normalized;
                }
            }
            else
            {
                // 普通网格或未烘焙的SkinnedMesh
                if (settings.useLocalSpace)
                {
                    worldVertex = meshTransform.TransformPoint(vertices[i]);
                    worldNormal = normals[i].normalized;
                }
                else
                {
                    worldVertex = meshTransform.TransformPoint(vertices[i]);
                    worldNormal = meshTransform.TransformDirection(normals[i]).normalized;
                }
            }
            
            // 可选：只显示朝向摄像机的法线
            if (settings.showOnlyVisible)
            {
                Camera sceneCamera = Camera.current;
                if (sceneCamera != null)
                {
                    Vector3 toCameraDirection = (sceneCamera.transform.position - worldVertex).normalized;
                    if (Vector3.Dot(worldNormal, toCameraDirection) <= 0)
                        continue;
                }
            }
            
            // 绘制法线
            Vector3 normalEnd = worldVertex + worldNormal * settings.normalLength;
            Gizmos.DrawLine(worldVertex, normalEnd);
            
            // 绘制法线箭头
            DrawArrowHead(worldVertex, normalEnd, settings.normalLength * 0.2f);
        }
    }
    
    private void DrawArrowHead(Vector3 start, Vector3 end, float arrowSize)
    {
        Vector3 direction = (end - start).normalized;
        Vector3 right = Vector3.Cross(direction, Vector3.up).normalized;
        Vector3 up = Vector3.Cross(right, direction).normalized;
        
        if (right == Vector3.zero)
        {
            right = Vector3.Cross(direction, Vector3.forward).normalized;
            up = Vector3.Cross(right, direction).normalized;
        }
        
        Vector3 arrowTip1 = end - direction * arrowSize + right * arrowSize * 0.5f;
        Vector3 arrowTip2 = end - direction * arrowSize - right * arrowSize * 0.5f;
        Vector3 arrowTip3 = end - direction * arrowSize + up * arrowSize * 0.5f;
        Vector3 arrowTip4 = end - direction * arrowSize - up * arrowSize * 0.5f;
        
        Gizmos.DrawLine(end, arrowTip1);
        Gizmos.DrawLine(end, arrowTip2);
        Gizmos.DrawLine(end, arrowTip3);
        Gizmos.DrawLine(end, arrowTip4);
    }

    public class BakeDataCustom
    {

        [HideInInspector] [SerializeField] public Matrix4x4[] bindPoses;
        [HideInInspector] public Vector3[] vertices;
        [HideInInspector] public Vector4[] tangents;
        [HideInInspector] public Vector3[] normals;
        [HideInInspector] public BoneWeight[] boneWeights;
        [HideInInspector] public int[] triangles;

        [HideInInspector] public Transform[] bones;

        public SkinnedMeshRenderer target;


        //[ContextMenu("Extract Bind Pose")]
        public void ExtractBindPose()
        {
            if (target && target.sharedMesh)
            {
                bindPoses = target.sharedMesh.bindposes;
                vertices = target.sharedMesh.vertices;
                boneWeights = target.sharedMesh.boneWeights;
                normals = target.sharedMesh.normals;
                tangents = target.sharedMesh.tangents;
                triangles = target.sharedMesh.triangles;
                bones = target.bones;
            }
        }

        /// <summary>
        /// 蒙皮矩阵  ：每根骨骼对应一个蒙皮矩阵，把其影响的顶点从bindpose转换到目前的pose
        /// </summary>
        /// <returns></returns>
        Matrix4x4[] SkinningMatrices()
        {
            Matrix4x4[] skinningMatrices = new Matrix4x4[bindPoses.Length];
            for (int i = 0; i < bindPoses.Length; i++)
            {
                Transform bone = bones[i];
                Matrix4x4 currentBoneWorldTransformationMatrix;
                if (bone)
                {
                    currentBoneWorldTransformationMatrix = bone.localToWorldMatrix;
                }
                else
                {
                    currentBoneWorldTransformationMatrix = target.transform.localToWorldMatrix * bindPoses[i].inverse;
                }

                skinningMatrices[i] = currentBoneWorldTransformationMatrix * bindPoses[i];
            }

            return skinningMatrices;
        }

        public void BakeOnCurrentPose(out Vector3[] poseVerts, out Vector3[] poseNormals, out Vector4[] poseTangents)
        {

            int numVerts = vertices.Length;
            poseVerts = new Vector3[numVerts];
            poseNormals = new Vector3[numVerts];
            poseTangents = new Vector4[numVerts];
            Matrix4x4[] skinningMatrices = SkinningMatrices();

            for (int i = 0; i < numVerts; i++)
            {
                BoneWeight boneWeight = boneWeights[i];
                Vector4 vert = vertices[i];
                vert.w = 1;

                Matrix4x4 skinningMatrix0 = skinningMatrices[boneWeight.boneIndex0];
                Matrix4x4 skinningMatrix1 = skinningMatrices[boneWeight.boneIndex1];
                Matrix4x4 skinningMatrix2 = skinningMatrices[boneWeight.boneIndex2];
                Matrix4x4 skinningMatrix3 = skinningMatrices[boneWeight.boneIndex3];

                float weight0 = boneWeight.weight0;
                float weight1 = boneWeight.weight1;
                float weight2 = boneWeight.weight2;
                float weight3 = boneWeight.weight3;

                Vector3 pos0 = skinningMatrix0 * vert;
                Vector3 pos1 = skinningMatrix1 * vert;
                Vector3 pos2 = skinningMatrix2 * vert;
                Vector3 pos3 = skinningMatrix3 * vert;

                Vector3 pos = pos0 * weight0 + pos1 * weight1 + pos2 * weight2 + pos3 * weight3;

                Vector3 norm = normals[i];

                Vector3 normal0 = skinningMatrix0 * norm;
                Vector3 normal1 = skinningMatrix1 * norm;
                Vector3 normal2 = skinningMatrix2 * norm;
                Vector3 normal3 = skinningMatrix3 * norm;

                Vector3 normal = normal0 * weight0 + normal1 * weight1 + normal2 * weight2 + normal3 * weight3;

                Vector4 tan = tangents[i];

                Vector3 tangent0 = skinningMatrix0 * tan;
                Vector3 tangent1 = skinningMatrix1 * tan;
                Vector3 tangent2 = skinningMatrix2 * tan;
                Vector3 tangent3 = skinningMatrix3 * tan;

                Vector4 tangent = tangent0 * weight0 + tangent1 * weight1 + tangent2 * weight2 + tangent3 * weight3;
                tangent.w = tan.w;

                poseVerts[i] = pos;
                poseNormals[i] = normal;
                poseTangents[i] = tangent;
            }
        }
    }

}
