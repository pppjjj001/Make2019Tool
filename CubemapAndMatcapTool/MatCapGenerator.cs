// MatCapGenerator.cs
// 放置路径: Assets/Scripts/TextureGeneration/MatCapGenerator.cs

using UnityEngine;
using UnityEngine.Rendering;
using System.IO;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace EnvironmentTextureBaker
{
    /// <summary>
    /// MatCap生成器 - 使用相机渲染方案
    /// 通过专用Layer隔离，传入采样位置
    /// </summary>
    public class MatCapGenerator : MonoBehaviour
    {
        #region 设置
        
        [Header("输入")]
        [Tooltip("用于生成MatCap的Cubemap")]
        public Cubemap sourceCubemap;
        
        [Header("采样位置")]
        [Tooltip("使用Transform指定采样位置")]
        public Transform samplePositionTransform;
        
        [Tooltip("手动指定采样位置（当Transform为空时使用）")]
        public Vector3 samplePosition = Vector3.zero;
        
        [Tooltip("Cubemap捕获时的位置")]
        public Vector3 cubemapCapturePosition = Vector3.zero;
        
        [Header("盒投影设置（室内场景）")]
        [Tooltip("启用盒投影校正")]
        public bool useBoxProjection = false;
        
        [Tooltip("盒投影范围")]
        public Vector3 boxProjectionSize = new Vector3(20f, 10f, 20f);
        
        [Header("分辨率")]
        public MatCapResolution resolution = MatCapResolution._512;
        
        [Header("PBR材质设置")]
        [Range(0f, 1f)]
        public float metallic = 0.5f;
        
        [Range(0f, 1f)]
        public float smoothness = 0.8f;
        
        public Color baseColor = Color.white;
        
        [Header("菲涅尔边缘设置 (中心留黑)")]
        public bool useFresnelMask = true;
        
        [Range(0.1f, 10f)]
        public float fresnelPower = 3f;
        
        [Range(0f, 3f)]
        public float fresnelScale = 1f;
        
        [Range(-1f, 1f)]
        public float fresnelBias = 0f;
        
        [Range(0f, 10f)]
        public float centerMaskPower = 2f;
        
        [Range(0f, 1f)]
        public float edgeThreshold = 0.3f;
        
        [Range(0f, 1f)]
        public float edgeSoftness = 0.2f;
        
        public Color centerColor = Color.black;
        
        [Header("高级设置")]
        [Range(0f, 5f)]
        public float environmentIntensity = 1f;
        
        public bool includeDiffuse = true;
        public bool includeSpecular = true;
        
        [Range(0f, 10f)]
        public float cubemapMipLevel = 0f;
        
        [Header("输出设置")]
        public string outputFolder = "Assets/GeneratedTextures/MatCaps";
        public string outputFileName = "GeneratedMatCap";
        public MatCapOutputFormat outputFormat = MatCapOutputFormat.PNG;
        
        [Header("背景")]
        public Color backgroundColor = new Color(0, 0, 0, 0);
        
        #endregion
        
        #region 枚举
        
        public enum MatCapResolution
        {
            _128 = 128,
            _256 = 256,
            _512 = 512,
            _1024 = 1024,
            _2048 = 2048
        }
        
        public enum MatCapOutputFormat
        {
            PNG,
            EXR,
            TGA
        }
        
        #endregion
        
        #region 常量
        
        // 使用一个不太可能被占用的Layer
        private const int BAKE_LAYER = 31;
        private const string BAKE_LAYER_NAME = "MatCapBake";
        
        #endregion
        
        #region 属性
        
        public Vector3 GetSamplePosition()
        {
            if (samplePositionTransform != null)
                return samplePositionTransform.position;
            return samplePosition;
        }
        
        #endregion
        
        #region 公共方法
        
        /// <summary>
        /// 生成MatCap贴图
        /// </summary>
        public Texture2D GenerateMatCap()
        {
            if (sourceCubemap == null)
            {
                Debug.LogError("Source Cubemap is not assigned!");
                return null;
            }
            
            int res = (int)resolution;
            
            // 确保Layer存在
            EnsureBakeLayer();
            
            // 创建渲染目标
            RenderTexture rt = RenderTexture.GetTemporary(res, res, 24, RenderTextureFormat.ARGBHalf);
            rt.antiAliasing = 8;
            
            // 创建烘焙场景
            GameObject bakeRoot = CreateBakeScene(rt);
            
            // 渲染
            Camera bakeCam = bakeRoot.GetComponentInChildren<Camera>();
            bakeCam.Render();
            
            // 读取结果
            RenderTexture.active = rt;
            Texture2D result = new Texture2D(res, res, TextureFormat.RGBAHalf, false);
            result.ReadPixels(new Rect(0, 0, res, res), 0, 0);
            result.Apply();
            RenderTexture.active = null;
            
            // 清理
            DestroyImmediate(bakeRoot);
            RenderTexture.ReleaseTemporary(rt);
            
            Vector3 pos = GetSamplePosition();
            Debug.Log($"MatCap generated at sample position ({pos.x:F2}, {pos.y:F2}, {pos.z:F2}) with resolution {res}x{res}");
            
            return result;
        }
        
        /// <summary>
        /// 在指定位置生成MatCap
        /// </summary>
        public Texture2D GenerateMatCapAtPosition(Vector3 worldPosition)
        {
            samplePosition = worldPosition;
            samplePositionTransform = null;
            return GenerateMatCap();
        }
        
        /// <summary>
        /// 同步Cubemap捕获位置到采样位置
        /// </summary>
        public void SyncSamplePositionFromCubemap()
        {
            samplePosition = cubemapCapturePosition;
            samplePositionTransform = null;
        }
        /// <summary>
        /// 生成 MatCap（内部调用）。
        /// </summary>
        /// <param name="sourceCubemap">环境 Cubemap</param>
        /// <param name="customBakeMaterial">
        ///   若为 null，则使用默认的 Hidden/MatCapBakeWithPosition；
        ///   否则直接使用传入的材质球（所有属性都来自该材质）。
        /// </param>
        public Texture2D GenerateMatCapInternal( Material customBakeMaterial = null)
        {
           
            if (sourceCubemap == null)
            {
                Debug.LogError("Source Cubemap is not assigned!");
                return null;
            }
            
            int res = (int)resolution;
            
            // 确保Layer存在
            EnsureBakeLayer();
            
            // 创建渲染目标
            RenderTexture rt = RenderTexture.GetTemporary(res, res, 24, RenderTextureFormat.ARGBHalf);
            rt.antiAliasing = 8;
            
            // 创建烘焙场景
            GameObject bakeRoot = CreateBakeScene(rt,customBakeMaterial);
            
            // 渲染
            Camera bakeCam = bakeRoot.GetComponentInChildren<Camera>();
            bakeCam.Render();
            
            // 读取结果
            RenderTexture.active = rt;
            Texture2D result = new Texture2D(res, res, TextureFormat.RGBAHalf, false);
            result.ReadPixels(new Rect(0, 0, res, res), 0, 0);
            result.Apply();
            RenderTexture.active = null;
            
            // 清理
            DestroyImmediate(bakeRoot);
            RenderTexture.ReleaseTemporary(rt);
            
            Vector3 pos = GetSamplePosition();
            Debug.Log($"MatCap generated at sample position ({pos.x:F2}, {pos.y:F2}, {pos.z:F2}) with resolution {res}x{res}");
            
            return result;
        }

        public Texture2D GenerateAndSaveMatCapCustomMat(Material customBakeMaterial)
        {
            Texture2D matcap = GenerateMatCapInternal(customBakeMaterial);

            if (matcap != null)
            {
#if UNITY_EDITOR
                SaveMatCap(matcap);
#endif
            }

            return matcap;
        }

        /// <summary>
        /// 生成并保存MatCap
        /// </summary>
        public Texture2D GenerateAndSaveMatCap()
        {
            Texture2D matcap = GenerateMatCap();
            
            if (matcap != null)
            {
                #if UNITY_EDITOR
                SaveMatCap(matcap);
                #endif
            }
            
            return matcap;
        }
        
        #if UNITY_EDITOR
        public void SaveMatCap(Texture2D matcap)
        {
            if (matcap == null)
            {
                Debug.LogError("MatCap texture is null!");
                return;
            }
            
            if (!Directory.Exists(outputFolder))
            {
                Directory.CreateDirectory(outputFolder);
            }
            
            string extension;
            byte[] bytes;
            
            switch (outputFormat)
            {
                case MatCapOutputFormat.PNG:
                    extension = "png";
                    Texture2D png8bit = ConvertTo8Bit(matcap);
                    bytes = png8bit.EncodeToPNG();
                    DestroyImmediate(png8bit);
                    break;
                    
                case MatCapOutputFormat.EXR:
                    extension = "exr";
                    bytes = matcap.EncodeToEXR(Texture2D.EXRFlags.CompressZIP);
                    break;
                    
                case MatCapOutputFormat.TGA:
                    extension = "tga";
                    bytes = matcap.EncodeToTGA();
                    break;
                    
                default:
                    extension = "png";
                    bytes = matcap.EncodeToPNG();
                    break;
            }
            
            string fullPath = $"{outputFolder}/{outputFileName}.{extension}";
            File.WriteAllBytes(fullPath, bytes);
            
            AssetDatabase.Refresh();
            
            TextureImporter importer = AssetImporter.GetAtPath(fullPath) as TextureImporter;
            if (importer != null)
            {
                importer.textureType = TextureImporterType.Default;
                importer.sRGBTexture = true;
                importer.alphaSource = TextureImporterAlphaSource.FromInput;
                importer.alphaIsTransparency = true;
                importer.mipmapEnabled = false;
                importer.wrapMode = TextureWrapMode.Clamp;
                importer.filterMode = FilterMode.Bilinear;
                importer.SaveAndReimport();
            }
            
            Debug.Log($"MatCap saved to {fullPath}");
        }
        
        private Texture2D ConvertTo8Bit(Texture2D source)
        {
            Texture2D result = new Texture2D(source.width, source.height, TextureFormat.RGBA32, false);
            Color[] pixels = source.GetPixels();
            
            for (int i = 0; i < pixels.Length; i++)
            {
                pixels[i].r = Mathf.LinearToGammaSpace(Mathf.Clamp01(pixels[i].r));
                pixels[i].g = Mathf.LinearToGammaSpace(Mathf.Clamp01(pixels[i].g));
                pixels[i].b = Mathf.LinearToGammaSpace(Mathf.Clamp01(pixels[i].b));
                pixels[i].a = Mathf.Clamp01(pixels[i].a);
            }
            
            result.SetPixels(pixels);
            result.Apply();
            return result;
        }
        #endif
        
        #endregion
        
        #region 私有方法
        
        private void EnsureBakeLayer()
        {
            #if UNITY_EDITOR
            // 检查Layer是否存在，如果不存在则尝试设置
            string layerName = LayerMask.LayerToName(BAKE_LAYER);
            if (string.IsNullOrEmpty(layerName) || layerName != BAKE_LAYER_NAME)
            {
                // 尝试设置Layer名称（需要在Editor中）
                SerializedObject tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
                SerializedProperty layers = tagManager.FindProperty("layers");
                
                SerializedProperty layerProp = layers.GetArrayElementAtIndex(BAKE_LAYER);
                if (layerProp != null && string.IsNullOrEmpty(layerProp.stringValue))
                {
                    layerProp.stringValue = BAKE_LAYER_NAME;
                    tagManager.ApplyModifiedProperties();
                    Debug.Log($"Created layer '{BAKE_LAYER_NAME}' at index {BAKE_LAYER}");
                }
            }
            #endif
        }
        
        /// <summary>
        /// 创建烘焙场景（相机+球体）
        /// </summary>
        private GameObject CreateBakeScene(RenderTexture targetRT,Material bakeMat = null)
        {
            // 根对象
            GameObject root = new GameObject("MatCapBakeScene");
            root.hideFlags = HideFlags.HideAndDontSave;
            
            // 创建相机
            GameObject camGO = new GameObject("BakeCamera");
            camGO.transform.SetParent(root.transform);
            camGO.transform.localPosition = new Vector3(0, 0, -3f);
            camGO.transform.localRotation = Quaternion.identity;
            
            Camera cam = camGO.AddComponent<Camera>();
            cam.orthographic = true;
            cam.orthographicSize = 1.001f;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 10f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = backgroundColor;
            cam.cullingMask = 1 << BAKE_LAYER;  // 只渲染烘焙Layer
            cam.targetTexture = targetRT;
            cam.allowHDR = true;
            cam.allowMSAA = true;
            
            // 禁用URP额外的相机数据（如果有的话）
            #if UNITY_2019_3_OR_NEWER
            var additionalCamData = camGO.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            if (additionalCamData == null)
            {
                additionalCamData = camGO.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            }
            additionalCamData.renderPostProcessing = false;
            additionalCamData.antialiasing = UnityEngine.Rendering.Universal.AntialiasingMode.None;
            #endif
            
            // 创建球体
            GameObject sphereGO = new GameObject("BakeSphere");
            sphereGO.transform.SetParent(root.transform);
            sphereGO.transform.localPosition = Vector3.zero;
            sphereGO.transform.localRotation = Quaternion.identity;
            sphereGO.transform.localScale = Vector3.one * 2f;
            sphereGO.layer = BAKE_LAYER;  // 设置到烘焙Layer
            
            // 添加网格
            MeshFilter mf = sphereGO.AddComponent<MeshFilter>();
            mf.sharedMesh = CreateSphereMesh(64, 64);
            
            MeshRenderer mr = sphereGO.AddComponent<MeshRenderer>();
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off;
            mr.reflectionProbeUsage = ReflectionProbeUsage.Off;

            if (bakeMat == null)
            {
                // 创建材质
                bakeMat = CreateBakeMaterial();
            }

            mr.sharedMaterial = bakeMat;
            
            return root;
        }
        
        /// <summary>
        /// 创建烘焙材质并设置参数
        /// </summary>
        private Material CreateBakeMaterial()
        {
            Shader bakeShader = Shader.Find("Hidden/MatCapBakeWithPosition");
            
            if (bakeShader == null)
            {
                Debug.LogError("Cannot find shader: Hidden/MatCapBakeWithPosition");
                return null;
            }
            
            Material mat = new Material(bakeShader);
            mat.hideFlags = HideFlags.HideAndDontSave;
            
            // Cubemap
            mat.SetTexture("_EnvironmentCubemap", sourceCubemap);
            mat.SetFloat("_EnvironmentIntensity", environmentIntensity);
            mat.SetFloat("_CubemapMipLevel", cubemapMipLevel);
            
            // 位置信息 - 关键！
            Vector3 samplePos = GetSamplePosition();
            mat.SetVector("_SampleWorldPosition", new Vector4(samplePos.x, samplePos.y, samplePos.z, 0));
            mat.SetVector("_CubemapCapturePosition", new Vector4(cubemapCapturePosition.x, cubemapCapturePosition.y, cubemapCapturePosition.z, 0));
            
            // 盒投影
            mat.SetFloat("_UseBoxProjection", useBoxProjection ? 1f : 0f);
            if (useBoxProjection)
            {
                Vector3 boxMin = cubemapCapturePosition - boxProjectionSize * 0.5f;
                Vector3 boxMax = cubemapCapturePosition + boxProjectionSize * 0.5f;
                mat.SetVector("_BoxProjectionMin", new Vector4(boxMin.x, boxMin.y, boxMin.z, 0));
                mat.SetVector("_BoxProjectionMax", new Vector4(boxMax.x, boxMax.y, boxMax.z, 0));
            }
            
            // PBR参数
            mat.SetColor("_BaseColor", baseColor);
            mat.SetFloat("_Metallic", metallic);
            mat.SetFloat("_Smoothness", smoothness);
            mat.SetFloat("_IncludeDiffuse", includeDiffuse ? 1f : 0f);
            mat.SetFloat("_IncludeSpecular", includeSpecular ? 1f : 0f);
            
            // 菲涅尔参数
            mat.SetFloat("_UseFresnelMask", useFresnelMask ? 1f : 0f);
            mat.SetFloat("_FresnelPower", fresnelPower);
            mat.SetFloat("_FresnelScale", fresnelScale);
            mat.SetFloat("_FresnelBias", fresnelBias);
            mat.SetFloat("_CenterMaskPower", centerMaskPower);
            mat.SetFloat("_EdgeThreshold", edgeThreshold);
            mat.SetFloat("_EdgeSoftness", edgeSoftness);
            mat.SetColor("_CenterColor", centerColor);
            
            return mat;
        }
        
        private static Mesh CreateSphereMesh(int longitudeSegments, int latitudeSegments)
        {
            Mesh mesh = new Mesh();
            mesh.name = "MatCapBakeSphere";
            
            int vertexCount = (longitudeSegments + 1) * (latitudeSegments + 1);
            Vector3[] vertices = new Vector3[vertexCount];
            Vector3[] normals = new Vector3[vertexCount];
            Vector2[] uvs = new Vector2[vertexCount];
            
            int index = 0;
            for (int lat = 0; lat <= latitudeSegments; lat++)
            {
                float theta = lat * Mathf.PI / latitudeSegments;
                float sinTheta = Mathf.Sin(theta);
                float cosTheta = Mathf.Cos(theta);
                
                for (int lon = 0; lon <= longitudeSegments; lon++)
                {
                    float phi = lon * 2f * Mathf.PI / longitudeSegments;
                    float sinPhi = Mathf.Sin(phi);
                    float cosPhi = Mathf.Cos(phi);
                    
                    Vector3 normal = new Vector3(cosPhi * sinTheta, cosTheta, sinPhi * sinTheta);
                    vertices[index] = normal * 0.5f;
                    normals[index] = normal;
                    uvs[index] = new Vector2((float)lon / longitudeSegments, (float)lat / latitudeSegments);
                    index++;
                }
            }
            
            int[] triangles = new int[longitudeSegments * latitudeSegments * 6];
            int triIndex = 0;
            
            for (int lat = 0; lat < latitudeSegments; lat++)
            {
                for (int lon = 0; lon < longitudeSegments; lon++)
                {
                    int current = lat * (longitudeSegments + 1) + lon;
                    int next = current + longitudeSegments + 1;
                    
                    triangles[triIndex++] = current;
                    triangles[triIndex++] = next;
                    triangles[triIndex++] = current + 1;
                    
                    triangles[triIndex++] = current + 1;
                    triangles[triIndex++] = next;
                    triangles[triIndex++] = next + 1;
                }
            }
            
            mesh.vertices = vertices;
            mesh.normals = normals;
            mesh.uv = uvs;
            mesh.triangles = triangles;
            mesh.RecalculateBounds();
            
            return mesh;
        }
        
        #endregion
        
        #region 编辑器可视化
        
        #if UNITY_EDITOR
        private void OnDrawGizmosSelected()
        {
            Vector3 samplePos = GetSamplePosition();
            
            // 采样位置
            Gizmos.color = Color.yellow;
            Gizmos.DrawWireSphere(samplePos, 0.3f);
            
            // 绘制坐标轴
            Gizmos.color = Color.red;
            Gizmos.DrawLine(samplePos, samplePos + Vector3.right * 0.5f);
            Gizmos.color = Color.green;
            Gizmos.DrawLine(samplePos, samplePos + Vector3.up * 0.5f);
            Gizmos.color = Color.blue;
            Gizmos.DrawLine(samplePos, samplePos + Vector3.forward * 0.5f);
            
            // Cubemap捕获位置
            Gizmos.color = Color.cyan;
            Gizmos.DrawWireSphere(cubemapCapturePosition, 0.2f);
            
            // 连线
            Gizmos.color = new Color(1, 1, 0, 0.5f);
            Gizmos.DrawLine(cubemapCapturePosition, samplePos);
            
            // 盒投影范围
            if (useBoxProjection)
            {
                Gizmos.color = new Color(0, 1, 1, 0.3f);
                Gizmos.DrawWireCube(cubemapCapturePosition, boxProjectionSize);
            }
        }
        #endif
        
        #endregion
    }
}
