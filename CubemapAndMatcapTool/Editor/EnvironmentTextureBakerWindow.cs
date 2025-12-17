// EnvironmentTextureBakerWindow.cs
// 放置路径: Assets/Editor/EnvironmentTextureBakerWindow.cs

#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;

namespace EnvironmentTextureBaker
{
    /// <summary>
    /// 环境贴图烘焙工具窗口
    /// </summary>
    public class EnvironmentTextureBakerWindow : EditorWindow
    {
        #region 窗口设置
        
        [MenuItem("Tools/TempByAI/Environment Texture Baker")]
        public static void ShowWindow()
        {
            var window = GetWindow<EnvironmentTextureBakerWindow>("环境贴图烘焙");
            window.minSize = new Vector2(400, 700);
        }
        
        #endregion
        
        #region 变量
        
        // Tab
        private int currentTab = 0;
        private string[] tabNames = { "Cubemap生成", "MatCap生成", "预览" };
        
        // Cubemap设置
        private Vector3 capturePosition = Vector3.zero;
        private Transform captureTransform;
        private CubemapGenerator.CubemapResolution cubemapResolution = CubemapGenerator.CubemapResolution._512;
        private bool cubemapHDR = true;
        private LayerMask cubemapCullingMask = -1;
        private CubemapGenerator.CubemapOutputFormat cubemapFormat = CubemapGenerator.CubemapOutputFormat.Asset;
        private string cubemapOutputPath = "Assets/GeneratedTextures/Cubemaps";
        private string cubemapFileName = "EnvironmentCubemap";
        
        // 生成的Cubemap
        private Cubemap generatedCubemap;
        
        // MatCap设置
        private Cubemap sourceCubemapForMatCap;
        private MatCapGenerator.MatCapResolution matcapResolution = MatCapGenerator.MatCapResolution._512;
        
        // PBR设置
        private float metallic = 0.5f;
        private float smoothness = 0.8f;
        private Color baseColor = Color.white;
        private float environmentIntensity = 1f;
        private bool includeDiffuse = true;
        private bool includeSpecular = true;
        private float cubemapMipLevel = 0f;
        
        // 菲涅尔设置
        private bool useFresnelMask = true;
        private float fresnelPower = 3f;
        private float fresnelScale = 1f;
        private float fresnelBias = 0f;
        private float centerMaskPower = 2f;
        private float edgeThreshold = 0.3f;
        private float edgeSoftness = 0.2f;
        private Color centerColor = Color.black;
        
        // MatCap输出
        private MatCapGenerator.MatCapOutputFormat matcapFormat = MatCapGenerator.MatCapOutputFormat.PNG;
        private string matcapOutputPath = "Assets/GeneratedTextures/MatCaps";
        private string matcapFileName = "GeneratedMatCap";
        
        // 生成的MatCap
        private Texture2D generatedMatCap;
        
        // 预览
        private Material previewMaterial;
        private PreviewRenderUtility previewRenderUtility;
        private Mesh previewMesh;
        private Vector2 previewRotation = new Vector2(0, 0);
        private float previewZoom = 2f;
        
        // 滚动
        private Vector2 scrollPosition;
        
        // 预设
        private int selectedPreset = 0;
        private string[] presetNames = { "自定义", "边缘发光", "轮廓线", "柔和光晕", "金属反射" };
        private Material customBakeMaterial;   // <-- 新增字段
        
        #endregion
        
        #region Unity回调
        
        private void OnEnable()
        {
            // 初始化预览
            if (previewRenderUtility == null)
            {
                previewRenderUtility = new PreviewRenderUtility();
                previewRenderUtility.cameraFieldOfView = 30f;
            }
            
            // 获取球体网格
            GameObject tempSphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            previewMesh = tempSphere.GetComponent<MeshFilter>().sharedMesh;
            DestroyImmediate(tempSphere);
        }
        
        private void OnDisable()
        {
            if (previewRenderUtility != null)
            {
                previewRenderUtility.Cleanup();
                previewRenderUtility = null;
            }
            
            if (previewMaterial != null)
            {
                DestroyImmediate(previewMaterial);
            }
        }
        
        private void OnGUI()
        {
            scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);
            
            // Tab栏
            EditorGUILayout.Space(10);
            currentTab = GUILayout.Toolbar(currentTab, tabNames, GUILayout.Height(30));
            EditorGUILayout.Space(10);
            
            switch (currentTab)
            {
                case 0:
                    DrawCubemapTab();
                    break;
                case 1:
                    DrawMatCapTab();
                    break;
                case 2:
                    DrawPreviewTab();
                    break;
            }
            
            EditorGUILayout.EndScrollView();
        }
        
        #endregion
        
        #region Cubemap Tab
        
        private void DrawCubemapTab()
        {
            EditorGUILayout.LabelField("Cubemap 生成设置", EditorStyles.boldLabel);
            EditorGUILayout.Space();
            
            // 捕获位置
            EditorGUILayout.LabelField("捕获位置", EditorStyles.miniBoldLabel);
            captureTransform = EditorGUILayout.ObjectField("位置Transform", captureTransform, typeof(Transform), true) as Transform;
            
            if (captureTransform == null)
            {
                capturePosition = EditorGUILayout.Vector3Field("手动位置", capturePosition);
            }
            else
            {
                EditorGUI.BeginDisabledGroup(true);
                EditorGUILayout.Vector3Field("当前位置", captureTransform.position);
                EditorGUI.EndDisabledGroup();
            }
            
            EditorGUILayout.Space();
            
            // 渲染设置
            EditorGUILayout.LabelField("渲染设置", EditorStyles.miniBoldLabel);
            cubemapResolution = (CubemapGenerator.CubemapResolution)EditorGUILayout.EnumPopup("分辨率", cubemapResolution);
            cubemapHDR = EditorGUILayout.Toggle("使用HDR", cubemapHDR);
            
            // LayerMask在Unity编辑器中的显示
            SerializedObject serializedObject = new SerializedObject(this);
            // 使用简化的方式
            cubemapCullingMask = EditorGUILayout.MaskField("渲染层级", cubemapCullingMask, GetLayerNames());
            
            EditorGUILayout.Space();
            
            // 输出设置
            EditorGUILayout.LabelField("输出设置", EditorStyles.miniBoldLabel);
            cubemapFormat = (CubemapGenerator.CubemapOutputFormat)EditorGUILayout.EnumPopup("输出格式", cubemapFormat);
            
            EditorGUILayout.BeginHorizontal();
            cubemapOutputPath = EditorGUILayout.TextField("输出路径", cubemapOutputPath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                string path = EditorUtility.OpenFolderPanel("选择输出文件夹", "Assets", "");
                if (!string.IsNullOrEmpty(path))
                {
                    if (path.StartsWith(Application.dataPath))
                    {
                        cubemapOutputPath = "Assets" + path.Substring(Application.dataPath.Length);
                    }
                }
            }
            EditorGUILayout.EndHorizontal();
            
            cubemapFileName = EditorGUILayout.TextField("文件名", cubemapFileName);
            
            EditorGUILayout.Space(20);
            
            // 生成按钮
            GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
            if (GUILayout.Button("生成 Cubemap", GUILayout.Height(40)))
            {
                GenerateCubemap();
            }
            GUI.backgroundColor = Color.white;
            
            EditorGUILayout.Space();
            
            // 显示生成的Cubemap
            if (generatedCubemap != null)
            {
                EditorGUILayout.LabelField("生成结果", EditorStyles.miniBoldLabel);
                EditorGUILayout.ObjectField("Cubemap", generatedCubemap, typeof(Cubemap), false);
                
                EditorGUILayout.Space();
                
                if (GUILayout.Button("使用此Cubemap生成MatCap"))
                {
                    sourceCubemapForMatCap = generatedCubemap;
                    currentTab = 1;
                }
            }
        }
        
        private string[] GetLayerNames()
        {
            string[] layers = new string[32];
            for (int i = 0; i < 32; i++)
            {
                string layerName = LayerMask.LayerToName(i);
                layers[i] = string.IsNullOrEmpty(layerName) ? $"Layer {i}" : layerName;
            }
            return layers;
        }
        
        private void GenerateCubemap()
        {
            Vector3 pos = captureTransform != null ? captureTransform.position : capturePosition;
            
            // 创建临时生成器
            GameObject tempGO = new GameObject("TempCubemapGenerator");
            CubemapGenerator generator = tempGO.AddComponent<CubemapGenerator>();
            tempGO.transform.position = pos;
            
            generator.resolution = cubemapResolution;
            generator.useHDR = cubemapHDR;
            generator.cullingMask = cubemapCullingMask;
            generator.outputFolder = cubemapOutputPath;
            generator.outputFileName = cubemapFileName;
            generator.outputFormat = cubemapFormat;
            
            generatedCubemap = generator.GenerateAndSaveCubemap();
            
            DestroyImmediate(tempGO);
            
            if (generatedCubemap != null)
            {
                EditorUtility.DisplayDialog("完成", "Cubemap生成成功！", "确定");
            }
        }
        
        #endregion
        
        #region MatCap Tab
        
        private void DrawMatCapTab()
        {
            EditorGUILayout.LabelField("MatCap 生成设置", EditorStyles.boldLabel);
            EditorGUILayout.Space();
            
            // 源Cubemap
            EditorGUILayout.LabelField("输入", EditorStyles.miniBoldLabel);
            sourceCubemapForMatCap = EditorGUILayout.ObjectField("源 Cubemap", sourceCubemapForMatCap, typeof(Cubemap), false) as Cubemap;
            
            if (sourceCubemapForMatCap == null)
            {
                EditorGUILayout.HelpBox("请先指定一个Cubemap作为环境光源", MessageType.Warning);
            }
            
            EditorGUILayout.Space();
            
            // 预设选择
            EditorGUILayout.LabelField("预设", EditorStyles.miniBoldLabel);
            int newPreset = EditorGUILayout.Popup("选择预设", selectedPreset, presetNames);
            if (newPreset != selectedPreset)
            {
                selectedPreset = newPreset;
                ApplyPreset(selectedPreset);
            }
            
            EditorGUILayout.Space();
            
            // 分辨率
            EditorGUILayout.LabelField("输出分辨率", EditorStyles.miniBoldLabel);
            matcapResolution = (MatCapGenerator.MatCapResolution)EditorGUILayout.EnumPopup("分辨率", matcapResolution);
            
            EditorGUILayout.Space();
            
            EditorGUILayout.LabelField("自定义材质球", EditorStyles.miniBoldLabel);
            customBakeMaterial = (Material)EditorGUILayout.ObjectField(
                "要使用的材质球",
                customBakeMaterial,
                typeof(Material),
                false);   // 自动显示当前已选中的材质

            if (customBakeMaterial == null)
            {
                // PBR设置
                EditorGUILayout.LabelField("PBR 材质设置", EditorStyles.miniBoldLabel);
                baseColor = EditorGUILayout.ColorField("基础颜色", baseColor);
                metallic = EditorGUILayout.Slider("金属度", metallic, 0f, 1f);
                smoothness = EditorGUILayout.Slider("光滑度", smoothness, 0f, 1f);
                environmentIntensity = EditorGUILayout.Slider("环境强度", environmentIntensity, 0f, 5f);
                cubemapMipLevel = EditorGUILayout.Slider("Cubemap模糊度", cubemapMipLevel, 0f, 10f);
                includeDiffuse = EditorGUILayout.Toggle("包含漫反射", includeDiffuse);
                includeSpecular = EditorGUILayout.Toggle("包含高光反射", includeSpecular);


                EditorGUILayout.Space();

                // 菲涅尔设置
                EditorGUILayout.LabelField("菲涅尔边缘效果 (中心留黑)", EditorStyles.miniBoldLabel);

                useFresnelMask = EditorGUILayout.Toggle("启用菲涅尔遮罩", useFresnelMask);

                if (useFresnelMask)
                {
                    EditorGUI.indentLevel++;

                    EditorGUILayout.HelpBox(
                        "菲涅尔效果使MatCap只在边缘显示环境反射，中心区域显示指定颜色（默认黑色）。\n" +
                        "• 幂次越大边缘越锐利\n" +
                        "• 中心遮罩越大黑色区域越大\n" +
                        "• 边缘阈值控制效果开始位置",
                        MessageType.Info);

                    fresnelPower = EditorGUILayout.Slider("菲涅尔幂次", fresnelPower, 0.1f, 10f);
                    fresnelScale = EditorGUILayout.Slider("菲涅尔强度", fresnelScale, 0f, 3f);
                    fresnelBias = EditorGUILayout.Slider("菲涅尔偏移", fresnelBias, -1f, 1f);

                    EditorGUILayout.Space(5);

                    centerMaskPower = EditorGUILayout.Slider("中心遮罩强度", centerMaskPower, 0f, 10f);
                    edgeThreshold = EditorGUILayout.Slider("边缘阈值", edgeThreshold, 0f, 1f);
                    edgeSoftness = EditorGUILayout.Slider("边缘软度", edgeSoftness, 0f, 1f);
                    centerColor = EditorGUILayout.ColorField("中心颜色", centerColor);

                    EditorGUI.indentLevel--;
                }
            }

            EditorGUILayout.Space();
            
            // 输出设置
            EditorGUILayout.LabelField("输出设置", EditorStyles.miniBoldLabel);
            matcapFormat = (MatCapGenerator.MatCapOutputFormat)EditorGUILayout.EnumPopup("输出格式", matcapFormat);
            
            EditorGUILayout.BeginHorizontal();
            matcapOutputPath = EditorGUILayout.TextField("输出路径", matcapOutputPath);
            if (GUILayout.Button("...", GUILayout.Width(30)))
            {
                string path = EditorUtility.OpenFolderPanel("选择输出文件夹", "Assets", "");
                if (!string.IsNullOrEmpty(path))
                {
                    if (path.StartsWith(Application.dataPath))
                    {
                        matcapOutputPath = "Assets" + path.Substring(Application.dataPath.Length);
                    }
                }
            }
            EditorGUILayout.EndHorizontal();
            
            matcapFileName = EditorGUILayout.TextField("文件名", matcapFileName);
            
            EditorGUILayout.Space(20);
            
            // 生成按钮
            EditorGUI.BeginDisabledGroup(sourceCubemapForMatCap == null);
            GUI.backgroundColor = new Color(0.4f, 0.6f, 1f);
            if (GUILayout.Button("生成 MatCap", GUILayout.Height(40)))
            {
                if (customBakeMaterial != null)
                {
                    GenerateMatCapCustomMat();
                }
                else
                {
                    GenerateMatCap();
                }
            }
            GUI.backgroundColor = Color.white;
            EditorGUI.EndDisabledGroup();
            
            EditorGUILayout.Space();
            
            // 显示生成的MatCap
            if (generatedMatCap != null)
            {
                EditorGUILayout.LabelField("生成结果", EditorStyles.miniBoldLabel);
                
                // 预览图
                Rect previewRect = GUILayoutUtility.GetRect(200, 200, GUILayout.ExpandWidth(true));
                EditorGUI.DrawPreviewTexture(previewRect, generatedMatCap, null, ScaleMode.ScaleToFit);
                
                EditorGUILayout.ObjectField("MatCap贴图", generatedMatCap, typeof(Texture2D), false);
            }
        }
        
        private void ApplyPreset(int preset)
        {
            switch (preset)
            {
                case 0: // 自定义
                    break;
                    
                case 1: // 边缘发光
                    useFresnelMask = true;
                    fresnelPower = 3f;
                    fresnelScale = 1.5f;
                    fresnelBias = 0f;
                    centerMaskPower = 4f;
                    edgeThreshold = 0.4f;
                    edgeSoftness = 0.3f;
                    centerColor = Color.black;
                    metallic = 0.8f;
                    smoothness = 0.9f;
                    break;
                    
                case 2: // 轮廓线
                    useFresnelMask = true;
                    fresnelPower = 6f;
                    fresnelScale = 2f;
                    fresnelBias = 0f;
                    centerMaskPower = 8f;
                    edgeThreshold = 0.2f;
                    edgeSoftness = 0.1f;
                    centerColor = Color.black;
                    metallic = 0.5f;
                    smoothness = 0.8f;
                    break;
                    
                case 3: // 柔和光晕
                    useFresnelMask = true;
                    fresnelPower = 1.5f;
                    fresnelScale = 1f;
                    fresnelBias = 0.1f;
                    centerMaskPower = 1f;
                    edgeThreshold = 0.6f;
                    edgeSoftness = 0.5f;
                    centerColor = new Color(0.1f, 0.1f, 0.1f);
                    metallic = 0.3f;
                    smoothness = 0.7f;
                    break;
                    
                case 4: // 金属反射
                    useFresnelMask = false;
                    metallic = 1f;
                    smoothness = 0.95f;
                    environmentIntensity = 1.2f;
                    break;
            }
        }
        private void GenerateMatCapCustomMat()
        {
            if (sourceCubemapForMatCap == null)
            {
                EditorUtility.DisplayDialog("错误", "请先指定源Cubemap！", "确定");
                return;
            }
            
            // 创建临时生成器
            GameObject tempGO = new GameObject("TempMatCapGenerator");
            MatCapGenerator generator = tempGO.AddComponent<MatCapGenerator>();
            
            // 设置参数
            generator.sourceCubemap = sourceCubemapForMatCap;
            generator.resolution = matcapResolution;
            
            generator.outputFolder = matcapOutputPath;
            generator.outputFileName = matcapFileName;
            generator.outputFormat = matcapFormat;
            
            generatedMatCap = generator.GenerateAndSaveMatCapCustomMat(customBakeMaterial);
            
            DestroyImmediate(tempGO);
            
            if (generatedMatCap != null)
            {
                EditorUtility.DisplayDialog("完成", "MatCap生成成功！", "确定");
            }
        }
        private void GenerateMatCap()
        {
            if (sourceCubemapForMatCap == null)
            {
                EditorUtility.DisplayDialog("错误", "请先指定源Cubemap！", "确定");
                return;
            }
            
            // 创建临时生成器
            GameObject tempGO = new GameObject("TempMatCapGenerator");
            MatCapGenerator generator = tempGO.AddComponent<MatCapGenerator>();
            
            // 设置参数
            generator.sourceCubemap = sourceCubemapForMatCap;
            generator.resolution = matcapResolution;
            
            generator.baseColor = baseColor;
            generator.metallic = metallic;
            generator.smoothness = smoothness;
            generator.environmentIntensity = environmentIntensity;
            generator.cubemapMipLevel = cubemapMipLevel;
            generator.includeDiffuse = includeDiffuse;
            generator.includeSpecular = includeSpecular;
            
            generator.useFresnelMask = useFresnelMask;
            generator.fresnelPower = fresnelPower;
            generator.fresnelScale = fresnelScale;
            generator.fresnelBias = fresnelBias;
            generator.centerMaskPower = centerMaskPower;
            generator.edgeThreshold = edgeThreshold;
            generator.edgeSoftness = edgeSoftness;
            generator.centerColor = centerColor;
            
            generator.outputFolder = matcapOutputPath;
            generator.outputFileName = matcapFileName;
            generator.outputFormat = matcapFormat;
            
            generatedMatCap = generator.GenerateAndSaveMatCap();
            
            DestroyImmediate(tempGO);
            
            if (generatedMatCap != null)
            {
                EditorUtility.DisplayDialog("完成", "MatCap生成成功！", "确定");
            }
        }
        
        #endregion
        
        #region Preview Tab
        
        private void DrawPreviewTab()
        {
            EditorGUILayout.LabelField("贴图预览", EditorStyles.boldLabel);
            EditorGUILayout.Space();
            
            // Cubemap预览
            EditorGUILayout.LabelField("Cubemap 预览", EditorStyles.miniBoldLabel);
            if (generatedCubemap != null)
            {
                // 简单的6面展示
                Rect cubemapRect = GUILayoutUtility.GetRect(300, 150, GUILayout.ExpandWidth(true));
                DrawCubemapPreview(cubemapRect, generatedCubemap);
            }
            else
            {
                EditorGUILayout.HelpBox("尚未生成Cubemap", MessageType.Info);
            }
            
            EditorGUILayout.Space(20);
            
            // MatCap预览
            EditorGUILayout.LabelField("MatCap 预览", EditorStyles.miniBoldLabel);
            if (generatedMatCap != null)
            {
                Rect matcapRect = GUILayoutUtility.GetRect(200, 200, GUILayout.ExpandWidth(true));
                EditorGUI.DrawPreviewTexture(matcapRect, generatedMatCap, null, ScaleMode.ScaleToFit);
            }
            else
            {
                EditorGUILayout.HelpBox("尚未生成MatCap", MessageType.Info);
            }
            
            EditorGUILayout.Space(20);
            
            // 3D预览
            EditorGUILayout.LabelField("3D 应用预览", EditorStyles.miniBoldLabel);
            if (generatedMatCap != null && previewRenderUtility != null)
            {
                Rect preview3DRect = GUILayoutUtility.GetRect(300, 300, GUILayout.ExpandWidth(true));
                Draw3DPreview(preview3DRect);
                
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField("拖拽旋转预览，滚轮缩放", EditorStyles.miniLabel);
                if (GUILayout.Button("重置视角", GUILayout.Width(80)))
                {
                    previewRotation = Vector2.zero;
                    previewZoom = 2f;
                }
                EditorGUILayout.EndHorizontal();
            }
        }
        
        private void DrawCubemapPreview(Rect rect, Cubemap cubemap)
        {
            // 简化的十字形布局预览
            float faceSize = Mathf.Min(rect.width / 4f, rect.height / 3f);
            
            // 这里只显示一个占位符，实际实现需要将Cubemap面提取为Texture2D
            EditorGUI.DrawRect(rect, new Color(0.2f, 0.2f, 0.2f));
            GUI.Label(rect, "Cubemap: " + cubemap.name, EditorStyles.centeredGreyMiniLabel);
        }
        
        private void Draw3DPreview(Rect rect)
        {
            // 处理输入
            Event e = Event.current;
            if (rect.Contains(e.mousePosition))
            {
                if (e.type == EventType.MouseDrag)
                {
                    previewRotation.x += e.delta.x;
                    previewRotation.y += e.delta.y;
                    previewRotation.y = Mathf.Clamp(previewRotation.y, -89f, 89f);
                    e.Use();
                    Repaint();
                }
                else if (e.type == EventType.ScrollWheel)
                {
                    previewZoom += e.delta.y * 0.1f;
                    previewZoom = Mathf.Clamp(previewZoom, 1f, 5f);
                    e.Use();
                    Repaint();
                }
            }
            
            // 设置预览材质
            if (previewMaterial == null)
            {
                previewMaterial = new Material(Shader.Find("Custom/URP/MatCapPreview"));
                if (previewMaterial.shader == null)
                {
                    previewMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                }
            }
            
            if (generatedMatCap != null)
            {
                previewMaterial.SetTexture("_MatCapTex", generatedMatCap);
            }
            
            // 渲染预览
            previewRenderUtility.BeginPreview(rect, GUIStyle.none);
            
            previewRenderUtility.camera.transform.position = new Vector3(0, 0, -previewZoom);
            previewRenderUtility.camera.transform.LookAt(Vector3.zero);
            
            Quaternion rotation = Quaternion.Euler(previewRotation.y, previewRotation.x, 0);
            
            previewRenderUtility.DrawMesh(previewMesh, Vector3.zero, rotation, previewMaterial, 0);
            previewRenderUtility.camera.Render();
            
            Texture resultTexture = previewRenderUtility.EndPreview();
            GUI.DrawTexture(rect, resultTexture);
        }
        
        #endregion
    }
}
#endif
