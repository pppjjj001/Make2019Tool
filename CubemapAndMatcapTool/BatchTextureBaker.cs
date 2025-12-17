// EnvironmentTextureBaker.cs
// 放置路径: Assets/Scripts/TextureGeneration/EnvironmentTextureBaker.cs

using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace EnvironmentTextureBaker
{
    /// <summary>
    /// 一体化环境贴图烘焙器
    /// 自动同步Cubemap位置到MatCap生成
    /// </summary>
    [ExecuteAlways]
    public class EnvironmentTextureBaker : MonoBehaviour
    {
        [Header("捕获位置")]
        [Tooltip("用作捕获位置的Transform，为空则使用自身位置")]
        public Transform capturePoint;
        
        [Header("Cubemap设置")]
        public CubemapGenerator.CubemapResolution cubemapResolution = CubemapGenerator.CubemapResolution._512;
        public bool cubemapHDR = true;
        public LayerMask cubemapCullingMask = -1;
        
        [Header("MatCap设置")]
        public MatCapGenerator.MatCapResolution matcapResolution = MatCapGenerator.MatCapResolution._512;
        
        [Header("PBR")]
        [Range(0f, 1f)] public float metallic = 0.5f;
        [Range(0f, 1f)] public float smoothness = 0.8f;
        public Color baseColor = Color.white;
        [Range(0f, 5f)] public float environmentIntensity = 1f;
        
        [Header("菲涅尔边缘")]
        public bool useFresnelMask = true;
        [Range(0.1f, 10f)] public float fresnelPower = 3f;
        [Range(0f, 3f)] public float fresnelScale = 1f;
        [Range(0f, 10f)] public float centerMaskPower = 2f;
        [Range(0f, 1f)] public float edgeThreshold = 0.3f;
        [Range(0f, 1f)] public float edgeSoftness = 0.2f;
        public Color centerColor = Color.black;
        
        [Header("盒投影（室内场景）")]
        public bool useBoxProjection = false;
        public Vector3 boxSize = new Vector3(20f, 10f, 20f);
        
        [Header("输出")]
        public string outputFolder = "Assets/GeneratedTextures";
        public string baseName = "Environment";
        
        [Header("生成结果")]
        [SerializeField] private Cubemap generatedCubemap;
        [SerializeField] private Texture2D generatedMatCap;
        
        /// <summary>
        /// 获取捕获位置
        /// </summary>
        public Vector3 CapturePosition
        {
            get
            {
                if (capturePoint != null)
                    return capturePoint.position;
                return transform.position;
            }
        }
        
        /// <summary>
        /// 一键生成Cubemap和MatCap
        /// </summary>
        public void BakeAll()
        {
            // 1. 生成Cubemap
            generatedCubemap = GenerateCubemap();
            
            if (generatedCubemap == null)
            {
                Debug.LogError("Failed to generate Cubemap!");
                return;
            }
            
            // 2. 使用同一位置生成MatCap
            generatedMatCap = GenerateMatCap(generatedCubemap);
            
            Debug.Log($"Baking complete! Cubemap and MatCap generated at position {CapturePosition}");
        }
        
        /// <summary>
        /// 仅生成Cubemap
        /// </summary>
        public Cubemap GenerateCubemap()
        {
            #if UNITY_EDITOR
            GameObject tempGO = new GameObject("TempCubemapGenerator");
            CubemapGenerator generator = tempGO.AddComponent<CubemapGenerator>();
            tempGO.transform.position = CapturePosition;
            
            generator.resolution = cubemapResolution;
            generator.useHDR = cubemapHDR;
            generator.cullingMask = cubemapCullingMask;
            generator.outputFolder = outputFolder + "/Cubemaps";
            generator.outputFileName = baseName + "_Cubemap";
            generator.outputFormat = CubemapGenerator.CubemapOutputFormat.Asset;
            
            Cubemap result = generator.GenerateAndSaveCubemap();
            
            DestroyImmediate(tempGO);
            return result;
            #else
            return null;
            #endif
        }
        
        /// <summary>
        /// 使用指定Cubemap生成MatCap
        /// </summary>
        public Texture2D GenerateMatCap(Cubemap cubemap)
        {
            if (cubemap == null)
            {
                Debug.LogError("Cubemap is null!");
                return null;
            }
            
            #if UNITY_EDITOR
            GameObject tempGO = new GameObject("TempMatCapGenerator");
            MatCapGenerator generator = tempGO.AddComponent<MatCapGenerator>();
            
            // 源Cubemap
            generator.sourceCubemap = cubemap;
            generator.resolution = matcapResolution;
            
            // 位置同步 - 关键！
            generator.samplePosition = CapturePosition;
            generator.cubemapCapturePosition = CapturePosition;
            
            // 盒投影
            generator.useBoxProjection = useBoxProjection;
            generator.boxProjectionSize = boxSize;
            
            // PBR
            generator.baseColor = baseColor;
            generator.metallic = metallic;
            generator.smoothness = smoothness;
            generator.environmentIntensity = environmentIntensity;
            
            // 菲涅尔
            generator.useFresnelMask = useFresnelMask;
            generator.fresnelPower = fresnelPower;
            generator.fresnelScale = fresnelScale;
            generator.centerMaskPower = centerMaskPower;
            generator.edgeThreshold = edgeThreshold;
            generator.edgeSoftness = edgeSoftness;
            generator.centerColor = centerColor;
            
            // 输出
            generator.outputFolder = outputFolder + "/MatCaps";
            generator.outputFileName = baseName + "_MatCap";
            generator.outputFormat = MatCapGenerator.MatCapOutputFormat.PNG;
            
            Texture2D result = generator.GenerateAndSaveMatCap();
            
            DestroyImmediate(tempGO);
            return result;
            #else
            return null;
            #endif
        }
        
        #if UNITY_EDITOR
        private void OnDrawGizmosSelected()
        {
            Vector3 pos = CapturePosition;
            
            // 捕获位置球
            Gizmos.color = Color.yellow;
            Gizmos.DrawWireSphere(pos, 0.5f);
            
            // 坐标轴
            float axisLength = 1f;
            Gizmos.color = Color.red;
            Gizmos.DrawLine(pos, pos + Vector3.right * axisLength);
            Gizmos.color = Color.green;
            Gizmos.DrawLine(pos, pos + Vector3.up * axisLength);
            Gizmos.color = Color.blue;
            Gizmos.DrawLine(pos, pos + Vector3.forward * axisLength);
            
            // 盒投影范围
            if (useBoxProjection)
            {
                Gizmos.color = new Color(0, 1, 1, 0.3f);
                Gizmos.DrawWireCube(pos, boxSize);
            }
            
            // 标签
            Handles.Label(pos + Vector3.up * 0.7f, "Capture Point");
        }
        #endif
    }
    
    #if UNITY_EDITOR
    [CustomEditor(typeof(EnvironmentTextureBaker))]
    public class EnvironmentTextureBakerEditor : Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();
            
            EditorGUILayout.Space(20);
            
            EnvironmentTextureBaker baker = (EnvironmentTextureBaker)target;
            
            // 显示当前位置
            EditorGUILayout.LabelField("当前捕获位置", baker.CapturePosition.ToString("F2"));
            
            EditorGUILayout.Space(10);
            
            // 按钮
            EditorGUILayout.BeginHorizontal();
            
            GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
            if (GUILayout.Button("生成 Cubemap", GUILayout.Height(35)))
            {
                baker.GenerateCubemap();
            }
            
            GUI.backgroundColor = new Color(0.4f, 0.6f, 1f);
            if (GUILayout.Button("生成 MatCap", GUILayout.Height(35)))
            {
                // 获取已有的Cubemap
                SerializedProperty cubemapProp = serializedObject.FindProperty("generatedCubemap");
                Cubemap cubemap = cubemapProp.objectReferenceValue as Cubemap;
                
                if (cubemap == null)
                {
                    EditorUtility.DisplayDialog("提示", "请先生成Cubemap！", "确定");
                }
                else
                {
                    baker.GenerateMatCap(cubemap);
                }
            }
            
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(5);
            
            GUI.backgroundColor = new Color(1f, 0.8f, 0.3f);
            if (GUILayout.Button("一键生成 Cubemap + MatCap", GUILayout.Height(45)))
            {
                baker.BakeAll();
            }
            
            GUI.backgroundColor = Color.white;
        }
    }
    #endif
}