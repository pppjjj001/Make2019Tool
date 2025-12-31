// using UnityEngine;
// using UnityEditor;
// using System.Collections.Generic;
// using System.Linq;
//
// public class HairAnalyzerVisualizer : EditorWindow
// {
//     private GameObject targetObject;
//     private Mesh analyzedMesh;
//     
//     // 分析结果
//     private List<HairStrip> hairStrips = new List<HairStrip>();
//     private int currentStripIndex = 0;
//     
//     // 可视化设置
//     private bool showAllStrips = true;
//     private bool showVertexLabels = true;
//     private bool showUVInfo = true;
//     private float vertexSphereSize = 0.002f;
//     
//     // 分析参数
//     private float rootThreshold = 0.05f;
//     private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
//     
//     private Vector2 scrollPos;
//     private bool analysisComplete = false;
//     
//     public enum AnalysisMethod
//     {
//         UVBased,           // 基于UV的V值
//         TriangleStrip,     // 基于三角形条带
//         ConnectedComponent // 基于连通分量
//     }
//     
//     /// <summary>
//     /// 毛发条带数据结构
//     /// </summary>
//     public class HairStrip
//     {
//         public int index;
//         public List<int> vertexIndices = new List<int>();
//         public List<int> triangleIndices = new List<int>(); // 三角形索引(每3个为一组)
//         public Color debugColor;
//         public float minV, maxV;
//         public Vector3 rootPosition;
//         public Vector3 tipPosition;
//         
//         // 统计信息
//         public int vertexCount => vertexIndices.Count;
//         public int triangleCount => triangleIndices.Count / 3;
//         public float vRange => maxV - minV;
//     }
//
//     [MenuItem("Tools/TempByAI/Hair/Hair Analyzer Visualizer")]
//     public static void ShowWindow()
//     {
//         var window = GetWindow<HairAnalyzerVisualizer>("毛发分析可视化");
//         window.minSize = new Vector2(400, 600);
//     }
//
//     private void OnEnable()
//     {
//         SceneView.duringSceneGui += OnSceneGUI;
//     }
//
//     private void OnDisable()
//     {
//         SceneView.duringSceneGui -= OnSceneGUI;
//     }
//
//     private void OnGUI()
//     {
//         scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
//         
//         DrawHeader();
//         DrawInputSection();
//         DrawAnalysisSettings();
//         DrawAnalysisButtons();
//         
//         if (analysisComplete)
//         {
//             DrawResultsSection();
//             DrawStripNavigator();
//             DrawVisualizationSettings();
//             DrawExportSection();
//         }
//         
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void DrawHeader()
//     {
//         EditorGUILayout.Space(10);
//         GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
//         {
//             fontSize = 16,
//             alignment = TextAnchor.MiddleCenter
//         };
//         GUILayout.Label("🔍 毛发结构分析与可视化工具", titleStyle);
//         EditorGUILayout.Space(10);
//     }
//
//     private void DrawInputSection()
//     {
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("输入", EditorStyles.boldLabel);
//         
//         EditorGUI.BeginChangeCheck();
//         targetObject = (GameObject)EditorGUILayout.ObjectField(
//             "目标物体", targetObject, typeof(GameObject), true);
//         if (EditorGUI.EndChangeCheck())
//         {
//             analysisComplete = false;
//             hairStrips.Clear();
//         }
//         
//         if (targetObject != null)
//         {
//             var mf = targetObject.GetComponent<MeshFilter>();
//             var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//             Mesh mesh = mf?.sharedMesh ?? smr?.sharedMesh;
//             
//             if (mesh != null)
//             {
//                 EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
//                 EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
//                 EditorGUILayout.LabelField("有顶点色", (mesh.colors != null && mesh.colors.Length > 0) ? "✓" : "✗");
//                 EditorGUILayout.LabelField("有UV", (mesh.uv != null && mesh.uv.Length > 0) ? "✓" : "✗");
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("分析设置", EditorStyles.boldLabel);
//         
//         analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
//         
//         EditorGUILayout.HelpBox(GetMethodDescription(analysisMethod), MessageType.Info);
//         
//         rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private string GetMethodDescription(AnalysisMethod method)
//     {
//         switch (method)
//         {
//             case AnalysisMethod.UVBased:
//                 return "基于UV：通过UV的V值识别根部(V低)和尖端(V高)，沿V值递增方向追踪毛发链。适用于UV规范铺设的毛发。";
//             case AnalysisMethod.TriangleStrip:
//                 return "基于三角形条带：分析三角形的连接关系，识别条带结构。适用于规则的四边形条带毛发。";
//             case AnalysisMethod.ConnectedComponent:
//                 return "基于连通分量：将不相连的三角形组分离成独立的毛发片。适用于每片毛发完全独立的情况。";
//             default:
//                 return "";
//         }
//     }
//
//     private void DrawAnalysisButtons()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUI.enabled = targetObject != null;
//         
//         if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
//         {
//             PerformAnalysis();
//         }
//         
//         GUI.enabled = true;
//     }
//
//     private void DrawResultsSection()
//     {
//         EditorGUILayout.Space(10);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
//         
//         EditorGUILayout.LabelField("识别到的毛发片数量", hairStrips.Count.ToString());
//         
//         if (hairStrips.Count > 0)
//         {
//             var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
//             var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
//             
//             EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} - {vertexCounts.Max()}");
//             EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} - {triCounts.Max()}");
//             EditorGUILayout.LabelField("平均顶点数", $"{vertexCounts.Average():F1}");
//             
//             // 检测异常
//             int abnormalCount = hairStrips.Count(s => s.vertexCount < 3 || s.vertexCount > 100);
//             if (abnormalCount > 0)
//             {
//                 EditorGUILayout.HelpBox($"检测到 {abnormalCount} 个可能异常的毛发片（顶点数过少或过多）", MessageType.Warning);
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawStripNavigator()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.BeginHorizontal();
//             
//             if (GUILayout.Button("◀ 上一片", GUILayout.Width(80)))
//             {
//                 currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             GUILayout.FlexibleSpace();
//             
//             currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
//             
//             GUILayout.FlexibleSpace();
//             
//             if (GUILayout.Button("下一片 ▶", GUILayout.Width(80)))
//             {
//                 currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             EditorGUILayout.EndHorizontal();
//             
//             // 显示当前毛发片信息
//             if (currentStripIndex < hairStrips.Count)
//             {
//                 var strip = hairStrips[currentStripIndex];
//                 EditorGUILayout.Space(5);
//                 
//                 EditorGUILayout.BeginVertical("helpbox");
//                 EditorGUILayout.LabelField($"毛发片 #{strip.index}", EditorStyles.boldLabel);
//                 EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString());
//                 EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
//                 EditorGUILayout.LabelField("UV V值范围", $"{strip.minV:F3} - {strip.maxV:F3}");
//                 EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F3}");
//                 
//                 // 显示顶点列表
//                 EditorGUILayout.Space(3);
//                 EditorGUILayout.LabelField("顶点索引:", string.Join(", ", strip.vertexIndices.Take(20)) + 
//                     (strip.vertexIndices.Count > 20 ? "..." : ""));
//                 
//                 EditorGUILayout.EndVertical();
//                 
//                 if (GUILayout.Button("聚焦到此毛发片"))
//                 {
//                     FocusOnStrip(currentStripIndex);
//                 }
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawVisualizationSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
//         
//         showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
//         showVertexLabels = EditorGUILayout.Toggle("显示顶点标签", showVertexLabels);
//         showUVInfo = EditorGUILayout.Toggle("显示UV信息", showUVInfo);
//         vertexSphereSize = EditorGUILayout.Slider("顶点球大小", vertexSphereSize, 0.0005f, 0.01f);
//         
//         if (GUILayout.Button("刷新Scene视图"))
//         {
//             SceneView.RepaintAll();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawExportSection()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📤 导出", EditorStyles.boldLabel);
//         
//         if (GUILayout.Button("导出当前毛发片为独立Mesh"))
//         {
//             ExportCurrentStripAsMesh();
//         }
//         
//         if (GUILayout.Button("导出所有毛发片为独立Mesh"))
//         {
//             ExportAllStripsAsMeshes();
//         }
//         
//         if (GUILayout.Button("生成带UV差值的Mesh"))
//         {
//             GenerateMeshWithUVDifference();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 执行分析
//     /// </summary>
//     private void PerformAnalysis()
//     {
//         if (targetObject == null) return;
//         
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         analyzedMesh = mf?.sharedMesh ?? smr?.sharedMesh;
//         
//         if (analyzedMesh == null)
//         {
//             EditorUtility.DisplayDialog("错误", "未找到Mesh", "确定");
//             return;
//         }
//         
//         hairStrips.Clear();
//         
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 AnalyzeByUV();
//                 break;
//             case AnalysisMethod.TriangleStrip:
//                 AnalyzeByTriangleStrip();
//                 break;
//             case AnalysisMethod.ConnectedComponent:
//                 AnalyzeByConnectedComponent();
//                 break;
//         }
//         
//         // 为每个毛发片分配随机颜色
//         System.Random rand = new System.Random(42);
//         foreach (var strip in hairStrips)
//         {
//             strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
//         }
//         
//         analysisComplete = true;
//         currentStripIndex = 0;
//         
//         Debug.Log($"分析完成！识别到 {hairStrips.Count} 个毛发片");
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 方法1：基于UV分析
//     /// </summary>
//     private void AnalyzeByUV()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         Vector3[] vertices = analyzedMesh.vertices;
//         int[] triangles = analyzedMesh.triangles;
//         
//         if (uvs == null || uvs.Length == 0)
//         {
//             EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//             return;
//         }
//         
//         // 构建邻接表
//         var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//         
//         // 构建顶点到三角形的映射
//         var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//         
//         // 找到所有根部顶点
//         float globalMinV = uvs.Min(uv => uv.y);
//         List<int> rootVertices = new List<int>();
//         
//         for (int i = 0; i < uvs.Length; i++)
//         {
//             if (uvs[i].y <= globalMinV + rootThreshold)
//             {
//                 // 确认是局部最小或边界
//                 bool hasLowerNeighbor = adjacency[i].Any(n => uvs[n].y < uvs[i].y - 0.001f);
//                 if (!hasLowerNeighbor)
//                 {
//                     rootVertices.Add(i);
//                 }
//             }
//         }
//         
//         Debug.Log($"找到 {rootVertices.Count} 个根部顶点");
//         
//         // 从根部顶点构建毛发链
//         HashSet<int> visitedVertices = new HashSet<int>();
//         int stripIndex = 0;
//         
//         foreach (int rootVert in rootVertices)
//         {
//             if (visitedVertices.Contains(rootVert))
//                 continue;
//             
//             HairStrip strip = new HairStrip { index = stripIndex++ };
//             HashSet<int> stripTriangles = new HashSet<int>();
//             
//             // BFS/DFS 追踪毛发链
//             Queue<int> queue = new Queue<int>();
//             queue.Enqueue(rootVert);
//             
//             while (queue.Count > 0)
//             {
//                 int current = queue.Dequeue();
//                 if (visitedVertices.Contains(current))
//                     continue;
//                 
//                 visitedVertices.Add(current);
//                 strip.vertexIndices.Add(current);
//                 
//                 // 收集相关三角形
//                 if (vertexToTriangles.ContainsKey(current))
//                 {
//                     foreach (int triIdx in vertexToTriangles[current])
//                     {
//                         stripTriangles.Add(triIdx);
//                     }
//                 }
//                 
//                 // 寻找相邻的、UV连续的顶点
//                 float currentV = uvs[current].y;
//                 foreach (int neighbor in adjacency[current])
//                 {
//                     if (visitedVertices.Contains(neighbor))
//                         continue;
//                     
//                     float neighborV = uvs[neighbor].y;
//                     float deltaV = Mathf.Abs(neighborV - currentV);
//                     
//                     // 判断是否属于同一条毛发
//                     // UV应该是连续的（V值变化不应该太大）
//                     if (deltaV < 0.3f) // 可调节的阈值
//                     {
//                         queue.Enqueue(neighbor);
//                     }
//                 }
//             }
//             
//             // 收集三角形索引
//             foreach (int triIdx in stripTriangles)
//             {
//                 strip.triangleIndices.Add(triangles[triIdx * 3]);
//                 strip.triangleIndices.Add(triangles[triIdx * 3 + 1]);
//                 strip.triangleIndices.Add(triangles[triIdx * 3 + 2]);
//             }
//             
//             // 计算统计信息
//             if (strip.vertexIndices.Count > 0)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//                 
//                 int rootIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//                 
//                 if (strip.vertexIndices.Count >= 2)
//                 {
//                     hairStrips.Add(strip);
//                 }
//             }
//         }
//     }
//
//     /// <summary>
//     /// 方法2：基于三角形条带分析
//     /// </summary>
//     private void AnalyzeByTriangleStrip()
//     {
//         int[] triangles = analyzedMesh.triangles;
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         // 构建边到三角形的映射
//         Dictionary<Edge, List<int>> edgeTriangles = new Dictionary<Edge, List<int>>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIndex = i / 3;
//             AddEdgeTriangle(edgeTriangles, triangles[i], triangles[i + 1], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 1], triangles[i + 2], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 2], triangles[i], triIndex);
//         }
//         
//         // 分组：通过共享边连接的三角形属于同一条带
//         int totalTriangles = triangles.Length / 3;
//         UnionFind uf = new UnionFind(totalTriangles);
//         
//         foreach (var kvp in edgeTriangles)
//         {
//             var tris = kvp.Value;
//             for (int i = 0; i < tris.Count - 1; i++)
//             {
//                 for (int j = i + 1; j < tris.Count; j++)
//                 {
//                     uf.Union(tris[i], tris[j]);
//                 }
//             }
//         }
//         
//         // 收集每个分组的三角形
//         Dictionary<int, List<int>> groups = new Dictionary<int, List<int>>();
//         for (int i = 0; i < totalTriangles; i++)
//         {
//             int root = uf.Find(i);
//             if (!groups.ContainsKey(root))
//                 groups[root] = new List<int>();
//             groups[root].Add(i);
//         }
//         
//         // 创建毛发片
//         int stripIndex = 0;
//         foreach (var group in groups.Values)
//         {
//             HairStrip strip = new HairStrip { index = stripIndex++ };
//             HashSet<int> vertSet = new HashSet<int>();
//             
//             foreach (int triIdx in group)
//             {
//                 int baseIdx = triIdx * 3;
//                 strip.triangleIndices.Add(triangles[baseIdx]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 1]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 2]);
//                 
//                 vertSet.Add(triangles[baseIdx]);
//                 vertSet.Add(triangles[baseIdx + 1]);
//                 vertSet.Add(triangles[baseIdx + 2]);
//             }
//             
//             strip.vertexIndices = vertSet.ToList();
//             
//             // 计算统计
//             if (uvs != null && uvs.Length > 0)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//             }
//             
//             if (strip.vertexIndices.Count > 0)
//             {
//                 var bounds = strip.vertexIndices.Select(v => vertices[v]);
//                 var center = bounds.Aggregate(Vector3.zero, (a, b) => a + b) / strip.vertexIndices.Count;
//                 strip.rootPosition = targetObject.transform.TransformPoint(center);
//                 strip.tipPosition = strip.rootPosition + Vector3.up * 0.01f;
//             }
//             
//             hairStrips.Add(strip);
//         }
//     }
//
//     /// <summary>
//     /// 方法3：基于连通分量分析
//     /// </summary>
//     private void AnalyzeByConnectedComponent()
//     {
//         // 与方法2类似，但使用更严格的连通性判断
//         AnalyzeByTriangleStrip();
//     }
//
//     /// <summary>
//     /// Scene视图绘制
//     /// </summary>
//     private void OnSceneGUI(SceneView sceneView)
//     {
//         if (!analysisComplete || targetObject == null || hairStrips.Count == 0)
//             return;
//         
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         Transform transform = targetObject.transform;
//         
//         Handles.matrix = Matrix4x4.identity;
//         
//         if (showAllStrips)
//         {
//             // 绘制所有毛发片（半透明）
//             foreach (var strip in hairStrips)
//             {
//                 DrawStrip(strip, vertices, uvs, transform, strip.index == currentStripIndex ? 1f : 0.3f);
//             }
//         }
//         else
//         {
//             // 只绘制当前毛发片
//             if (currentStripIndex < hairStrips.Count)
//             {
//                 DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
//             }
//         }
//     }
//
//     private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
//     {
//         Color stripColor = strip.debugColor;
//         stripColor.a = alpha;
//         
//         // 绘制三角形面
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             
//             Handles.DrawAAConvexPolygon(v0, v1, v2);
//         }
//         
//         // 绘制边框
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             
//             Handles.DrawLine(v0, v1);
//             Handles.DrawLine(v1, v2);
//             Handles.DrawLine(v2, v0);
//         }
//         
//         // 绘制顶点
//         foreach (int vertIdx in strip.vertexIndices)
//         {
//             Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
//             
//             // 根据UV的V值着色
//             float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;
//             Color vertColor = Color.Lerp(Color.red, Color.blue, (vValue - strip.minV) / Mathf.Max(strip.vRange, 0.001f));
//             vertColor.a = alpha;
//             
//             Handles.color = vertColor;
//             Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);
//             
//             // 显示标签
//             if (showVertexLabels && alpha > 0.5f)
//             {
//                 string label = $"{vertIdx}";
//                 if (showUVInfo && uvs != null)
//                 {
//                     label += $"\nV:{vValue:F2}";
//                 }
//                 Handles.Label(worldPos + Vector3.up * vertexSphereSize, label);
//             }
//         }
//         
//         // 绘制根部到尖端的线
//         if (alpha > 0.5f)
//         {
//             Handles.color = Color.yellow;
//             Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 2f);
//             
//             Handles.color = Color.green;
//             Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2, EventType.Repaint);
//             Handles.Label(strip.rootPosition, "ROOT");
//             
//             Handles.color = Color.cyan;
//             Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2, EventType.Repaint);
//             Handles.Label(strip.tipPosition, "TIP");
//         }
//     }
//
//     private void FocusOnStrip(int index)
//     {
//         if (index >= hairStrips.Count) return;
//         
//         var strip = hairStrips[index];
//         Vector3 center = (strip.rootPosition + strip.tipPosition) / 2;
//         float size = Vector3.Distance(strip.rootPosition, strip.tipPosition) * 2;
//         
//         SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, Mathf.Max(size, 0.1f));
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 导出当前毛发片
//     /// </summary>
//     private void ExportCurrentStripAsMesh()
//     {
//         if (currentStripIndex >= hairStrips.Count) return;
//         
//         var strip = hairStrips[currentStripIndex];
//         Mesh newMesh = CreateMeshFromStrip(strip);
//         
//         string path = EditorUtility.SaveFilePanelInProject(
//             "保存毛发片Mesh", $"HairStrip_{strip.index}", "asset", "选择保存位置");
//         
//         if (!string.IsNullOrEmpty(path))
//         {
//             AssetDatabase.CreateAsset(newMesh, path);
//             AssetDatabase.SaveAssets();
//             Debug.Log($"毛发片已导出到: {path}");
//         }
//     }
//
//     /// <summary>
//     /// 导出所有毛发片
//     /// </summary>
//     private void ExportAllStripsAsMeshes()
//     {
//         string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
//         if (string.IsNullOrEmpty(folder)) return;
//         
//         // 转换为相对路径
//         if (folder.StartsWith(Application.dataPath))
//         {
//             folder = "Assets" + folder.Substring(Application.dataPath.Length);
//         }
//         
//         foreach (var strip in hairStrips)
//         {
//             Mesh mesh = CreateMeshFromStrip(strip);
//             string path = $"{folder}/HairStrip_{strip.index}.asset";
//             AssetDatabase.CreateAsset(mesh, path);
//         }
//         
//         AssetDatabase.SaveAssets();
//         Debug.Log($"已导出 {hairStrips.Count} 个毛发片到 {folder}");
//     }
//
//     private Mesh CreateMeshFromStrip(HairStrip strip)
//     {
//         Vector3[] origVertices = analyzedMesh.vertices;
//         Vector2[] origUVs = analyzedMesh.uv;
//         Vector3[] origNormals = analyzedMesh.normals;
//         Color[] origColors = analyzedMesh.colors;
//         
//         // 重映射顶点索引
//         Dictionary<int, int> vertexRemap = new Dictionary<int, int>();
//         for (int i = 0; i < strip.vertexIndices.Count; i++)
//         {
//             vertexRemap[strip.vertexIndices[i]] = i;
//         }
//         
//         // 创建新的顶点数据
//         Vector3[] newVertices = strip.vertexIndices.Select(v => origVertices[v]).ToArray();
//         Vector2[] newUVs = strip.vertexIndices.Select(v => origUVs != null && v < origUVs.Length ? origUVs[v] : Vector2.zero).ToArray();
//         Vector3[] newNormals = strip.vertexIndices.Select(v => origNormals != null && v < origNormals.Length ? origNormals[v] : Vector3.up).ToArray();
//         
//         // 重映射三角形
//         int[] newTriangles = new int[strip.triangleIndices.Count];
//         for (int i = 0; i < strip.triangleIndices.Count; i++)
//         {
//             newTriangles[i] = vertexRemap[strip.triangleIndices[i]];
//         }
//         
//         // 计算UV差值并存储到顶点颜色
//         Color[] newColors = new Color[newVertices.Length];
//         for (int i = 0; i < strip.vertexIndices.Count; i++)
//         {
//             float v = newUVs[i].y;
//             float diff = strip.vRange > 0.001f ? (strip.maxV - v) / strip.vRange : 0;
//             newColors[i] = new Color(1, 1, diff, 1);
//         }
//         
//         Mesh mesh = new Mesh();
//         mesh.name = $"HairStrip_{strip.index}";
//         mesh.vertices = newVertices;
//         mesh.uv = newUVs;
//         mesh.normals = newNormals;
//         mesh.colors = newColors;
//         mesh.triangles = newTriangles;
//         mesh.RecalculateBounds();
//         
//         return mesh;
//     }
//
//     /// <summary>
//     /// 生成带UV差值的完整Mesh
//     /// </summary>
//     private void GenerateMeshWithUVDifference()
//     {
//         Mesh newMesh = Instantiate(analyzedMesh);
//         newMesh.name = analyzedMesh.name + "_WithUVDiff";
//         
//         Vector2[] uvs = newMesh.uv;
//         Color[] colors = new Color[newMesh.vertexCount];
//         
//         // 初始化为白色
//         for (int i = 0; i < colors.Length; i++)
//         {
//             colors[i] = Color.white;
//         }
//         
//         // 为每个毛发片的顶点计算差值
//         foreach (var strip in hairStrips)
//         {
//             foreach (int vertIdx in strip.vertexIndices)
//             {
//                 float v = uvs[vertIdx].y;
//                 float diff = strip.vRange > 0.001f ? (strip.maxV - v) / strip.vRange : 0;
//                 colors[vertIdx].b = diff;
//             }
//         }
//         
//         newMesh.colors = colors;
//         
//         // 应用到物体
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         
//         if (mf != null) mf.sharedMesh = newMesh;
//         else if (smr != null) smr.sharedMesh = newMesh;
//         
//         // 保存
//         string path = EditorUtility.SaveFilePanelInProject(
//             "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");
//         
//         if (!string.IsNullOrEmpty(path))
//         {
//             AssetDatabase.CreateAsset(newMesh, path);
//             AssetDatabase.SaveAssets();
//         }
//         
//         Debug.Log("UV差值已计算并存储到顶点颜色B通道");
//     }
//
//     #region Helper Methods
//     
//     private Dictionary<int, HashSet<int>> BuildAdjacencyList(int[] triangles, int vertexCount)
//     {
//         var adjacency = new Dictionary<int, HashSet<int>>();
//         for (int i = 0; i < vertexCount; i++)
//             adjacency[i] = new HashSet<int>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
//             adjacency[v0].Add(v1); adjacency[v0].Add(v2);
//             adjacency[v1].Add(v0); adjacency[v1].Add(v2);
//             adjacency[v2].Add(v0); adjacency[v2].Add(v1);
//         }
//         
//         return adjacency;
//     }
//     
//     private Dictionary<int, List<int>> BuildVertexToTrianglesMap(int[] triangles)
//     {
//         var map = new Dictionary<int, List<int>>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIdx = i / 3;
//             for (int j = 0; j < 3; j++)
//             {
//                 int v = triangles[i + j];
//                 if (!map.ContainsKey(v))
//                     map[v] = new List<int>();
//                 map[v].Add(triIdx);
//             }
//         }
//         
//         return map;
//     }
//     
//     private void AddEdgeTriangle(Dictionary<Edge, List<int>> dict, int v0, int v1, int triIndex)
//     {
//         Edge edge = new Edge(v0, v1);
//         if (!dict.ContainsKey(edge))
//             dict[edge] = new List<int>();
//         dict[edge].Add(triIndex);
//     }
//     
//     public struct Edge : System.IEquatable<Edge>
//     {
//         public int v0, v1;
//         
//         public Edge(int a, int b)
//         {
//             v0 = Mathf.Min(a, b);
//             v1 = Mathf.Max(a, b);
//         }
//         
//         public bool Equals(Edge other) => v0 == other.v0 && v1 == other.v1;
//         public override int GetHashCode() => v0.GetHashCode() ^ (v1.GetHashCode() << 16);
//     }
//     
//     public class UnionFind
//     {
//         private int[] parent, rank;
//         
//         public UnionFind(int n)
//         {
//             parent = new int[n];
//             rank = new int[n];
//             for (int i = 0; i < n; i++) parent[i] = i;
//         }
//         
//         public int Find(int x)
//         {
//             if (parent[x] != x) parent[x] = Find(parent[x]);
//             return parent[x];
//         }
//         
//         public void Union(int x, int y)
//         {
//             int px = Find(x), py = Find(y);
//             if (px == py) return;
//             if (rank[px] < rank[py]) parent[px] = py;
//             else if (rank[px] > rank[py]) parent[py] = px;
//             else { parent[py] = px; rank[px]++; }
//         }
//     }
//     
//     #endregion
// }
//---------------------上面屏蔽是因为用的V最小当根节点,下面是改成V最大当根节点,细节也有些许变化------------------------------

// using UnityEngine;
// using UnityEditor;
// using System.Collections.Generic;
// using System.Linq;
//
// public class HairAnalyzerVisualizer : EditorWindow
// {
//     private GameObject targetObject;
//     private Mesh analyzedMesh;
//     
//     // 分析结果
//     private List<HairStrip> hairStrips = new List<HairStrip>();
//     private int currentStripIndex = 0;
//     
//     // 可视化设置
//     private bool showAllStrips = true;
//     private bool showVertexLabels = false;
//     private bool showUVInfo = true;
//     private bool showRootTipMarkers = true;
//     private float vertexSphereSize = 0.002f;
//     
//     // 分析参数
//     private float rootThreshold = 0.05f;
//     private float uvContinuityThreshold = 0.3f;
//     private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
//     
//     private Vector2 scrollPos;
//     private bool analysisComplete = false;
//     
//     public enum AnalysisMethod
//     {
//         UVBased,
//         TriangleStrip,
//         ConnectedComponent
//     }
//
//     /// <summary>
//     /// 毛发条带数据
//     /// </summary>
//     public class HairStrip
//     {
//         public int index;
//         public List<int> vertexIndices = new List<int>();
//         public List<int> triangleIndices = new List<int>();
//         public Color debugColor;
//         
//         // UV统计 - 注意：maxV是根部，minV是尖端
//         public float minV; // 尖端（TIP）
//         public float maxV; // 根部（ROOT）
//         
//         public Vector3 rootPosition; // V值最大的点
//         public Vector3 tipPosition;  // V值最小的点
//         
//         public int vertexCount => vertexIndices.Count;
//         public int triangleCount => triangleIndices.Count / 3;
//         public float vRange => maxV - minV;
//     }
//
//     [MenuItem("Tools/Hair/Hair Analyzer Visualizer")]
//     public static void ShowWindow()
//     {
//         var window = GetWindow<HairAnalyzerVisualizer>("毛发分析可视化");
//         window.minSize = new Vector2(420, 700);
//     }
//
//     private void OnEnable()
//     {
//         SceneView.duringSceneGui += OnSceneGUI;
//     }
//
//     private void OnDisable()
//     {
//         SceneView.duringSceneGui -= OnSceneGUI;
//     }
//
//     private void OnGUI()
//     {
//         scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
//         
//         DrawHeader();
//         DrawInputSection();
//         DrawAnalysisSettings();
//         DrawAnalysisButtons();
//         
//         if (analysisComplete)
//         {
//             DrawResultsSection();
//             DrawStripNavigator();
//             DrawVisualizationSettings();
//             DrawExportSection();
//         }
//         
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void DrawHeader()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
//         {
//             fontSize = 16,
//             alignment = TextAnchor.MiddleCenter
//         };
//         GUILayout.Label("🔍 毛发结构分析与可视化", titleStyle);
//         
//         EditorGUILayout.Space(5);
//         
//         EditorGUILayout.HelpBox(
//             "UV规则：\n" +
//             "• ROOT（根部）= V值最大 → 显示为绿色\n" +
//             "• TIP（尖端）= V值最小 → 显示为红色\n" +
//             "• 差值结果：根部=1，尖端=0", 
//             MessageType.Info);
//         
//         EditorGUILayout.Space(10);
//     }
//
//     private void DrawInputSection()
//     {
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📥 输入", EditorStyles.boldLabel);
//         
//         EditorGUI.BeginChangeCheck();
//         targetObject = (GameObject)EditorGUILayout.ObjectField(
//             "目标物体", targetObject, typeof(GameObject), true);
//         if (EditorGUI.EndChangeCheck())
//         {
//             analysisComplete = false;
//             hairStrips.Clear();
//         }
//         
//         if (targetObject != null)
//         {
//             Mesh mesh = GetMesh();
//             if (mesh != null)
//             {
//                 EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
//                 EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
//                 
//                 if (mesh.uv != null && mesh.uv.Length > 0)
//                 {
//                     float minV = mesh.uv.Min(uv => uv.y);
//                     float maxV = mesh.uv.Max(uv => uv.y);
//                     EditorGUILayout.LabelField("UV V值范围", $"{minV:F3} ~ {maxV:F3}");
//                 }
//                 else
//                 {
//                     EditorGUILayout.HelpBox("警告：Mesh没有UV数据！", MessageType.Warning);
//                 }
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("⚙️ 分析设置", EditorStyles.boldLabel);
//         
//         analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
//         
//         string methodDesc = "";
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 methodDesc = "从V值最大的点(根部)出发，沿V递减方向追踪";
//                 break;
//             case AnalysisMethod.TriangleStrip:
//                 methodDesc = "通过共享边的三角形分组";
//                 break;
//             case AnalysisMethod.ConnectedComponent:
//                 methodDesc = "完全独立的三角形组为一片";
//                 break;
//         }
//         EditorGUILayout.HelpBox(methodDesc, MessageType.None);
//         
//         rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
//         uvContinuityThreshold = EditorGUILayout.Slider("UV连续性阈值", uvContinuityThreshold, 0.1f, 0.5f);
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisButtons()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUI.enabled = targetObject != null && GetMesh() != null;
//         
//         GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
//         if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
//         {
//             PerformAnalysis();
//         }
//         GUI.backgroundColor = Color.white;
//         
//         GUI.enabled = true;
//     }
//
//     private void DrawResultsSection()
//     {
//         EditorGUILayout.Space(10);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
//         
//         EditorGUILayout.LabelField("识别到的毛发片", hairStrips.Count.ToString());
//         
//         if (hairStrips.Count > 0)
//         {
//             var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
//             var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
//             var vRanges = hairStrips.Select(s => s.vRange).ToList();
//             
//             EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} ~ {vertexCounts.Max()} (平均:{vertexCounts.Average():F1})");
//             EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} ~ {triCounts.Max()}");
//             EditorGUILayout.LabelField("V值跨度范围", $"{vRanges.Min():F3} ~ {vRanges.Max():F3}");
//             
//             // 检测异常
//             int tooSmall = hairStrips.Count(s => s.vertexCount < 3);
//             int tooLarge = hairStrips.Count(s => s.vertexCount > 50);
//             int noVRange = hairStrips.Count(s => s.vRange < 0.01f);
//             
//             if (tooSmall > 0 || tooLarge > 0 || noVRange > 0)
//             {
//                 string warning = "检测到异常：\n";
//                 if (tooSmall > 0) warning += $"• {tooSmall} 片顶点数过少(<3)\n";
//                 if (tooLarge > 0) warning += $"• {tooLarge} 片顶点数过多(>50)\n";
//                 if (noVRange > 0) warning += $"• {noVRange} 片V值跨度过小(<0.01)";
//                 EditorGUILayout.HelpBox(warning, MessageType.Warning);
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawStripNavigator()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.BeginHorizontal();
//             
//             if (GUILayout.Button("◀", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
//             
//             if (GUILayout.Button("▶", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             EditorGUILayout.EndHorizontal();
//             
//             // 当前毛发片详情
//             if (currentStripIndex < hairStrips.Count)
//             {
//                 var strip = hairStrips[currentStripIndex];
//                 
//                 EditorGUILayout.Space(5);
//                 EditorGUILayout.BeginVertical("helpbox");
//                 
//                 EditorGUILayout.LabelField($"毛发片 #{strip.index}", EditorStyles.boldLabel);
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString(), GUILayout.Width(150));
//                 EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("根部V值(MAX)", $"{strip.maxV:F4}", GUILayout.Width(150));
//                 EditorGUILayout.LabelField("尖端V值(MIN)", $"{strip.minV:F4}");
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F4}");
//                 
//                 // 顶点列表预览
//                 string vertPreview = string.Join(", ", strip.vertexIndices.Take(15));
//                 if (strip.vertexIndices.Count > 15) vertPreview += "...";
//                 EditorGUILayout.LabelField("顶点:", vertPreview, EditorStyles.miniLabel);
//                 
//                 EditorGUILayout.EndVertical();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 if (GUILayout.Button("聚焦此片"))
//                 {
//                     FocusOnStrip(currentStripIndex);
//                 }
//                 if (GUILayout.Button("导出此片"))
//                 {
//                     ExportSingleStrip(strip);
//                 }
//                 EditorGUILayout.EndHorizontal();
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawVisualizationSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
//         
//         showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
//         showVertexLabels = EditorGUILayout.Toggle("显示顶点索引", showVertexLabels);
//         showUVInfo = EditorGUILayout.Toggle("显示UV V值", showUVInfo);
//         showRootTipMarkers = EditorGUILayout.Toggle("显示根部/尖端标记", showRootTipMarkers);
//         vertexSphereSize = EditorGUILayout.Slider("顶点大小", vertexSphereSize, 0.0005f, 0.02f);
//         
//         EditorGUILayout.BeginHorizontal();
//         if (GUILayout.Button("刷新视图"))
//         {
//             SceneView.RepaintAll();
//         }
//         if (GUILayout.Button("重置相机"))
//         {
//             if (targetObject != null)
//             {
//                 SceneView.lastActiveSceneView?.LookAt(targetObject.transform.position);
//             }
//         }
//         EditorGUILayout.EndHorizontal();
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawExportSection()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📤 导出", EditorStyles.boldLabel);
//         
//         if (GUILayout.Button("生成带UV差值的Mesh"))
//         {
//             GenerateMeshWithUVDifference();
//         }
//         
//         if (GUILayout.Button("导出所有毛发片"))
//         {
//             ExportAllStrips();
//         }
//         
//         if (GUILayout.Button("导出分析报告"))
//         {
//             ExportAnalysisReport();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 执行分析
//     /// </summary>
//     private void PerformAnalysis()
//     {
//         analyzedMesh = GetMesh();
//         if (analyzedMesh == null) return;
//         
//         hairStrips.Clear();
//         
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 AnalyzeByUV();
//                 break;
//             case AnalysisMethod.TriangleStrip:
//             case AnalysisMethod.ConnectedComponent:
//                 AnalyzeByConnectedComponent();
//                 break;
//         }
//         
//         // 分配随机颜色
//         System.Random rand = new System.Random(42);
//         foreach (var strip in hairStrips)
//         {
//             strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
//         }
//         
//         analysisComplete = true;
//         currentStripIndex = 0;
//         
//         Debug.Log($"✓ 分析完成！识别到 {hairStrips.Count} 个毛发片");
//         SceneView.RepaintAll();
//     }
//
//     // /// <summary>
//     // /// 基于UV分析（ROOT = V值最大）
//     // /// </summary>
//     // private void AnalyzeByUV()
//     // {
//     //     Vector2[] uvs = analyzedMesh.uv;
//     //     Vector3[] vertices = analyzedMesh.vertices;
//     //     int[] triangles = analyzedMesh.triangles;
//     //     
//     //     if (uvs == null || uvs.Length == 0)
//     //     {
//     //         EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//     //         return;
//     //     }
//     //     
//     //     // 构建邻接表和顶点-三角形映射
//     //     var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//     //     var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//     //     
//     //     // 找根部顶点（V值最大）
//     //     float globalMaxV = uvs.Max(uv => uv.y);
//     //     List<int> rootVertices = new List<int>();
//     //     
//     //     for (int i = 0; i < uvs.Length; i++)
//     //     {
//     //         // V值接近全局最大
//     //         if (uvs[i].y >= globalMaxV - rootThreshold)
//     //         {
//     //             rootVertices.Add(i);
//     //             continue;
//     //         }
//     //         
//     //         // 或者是局部最大
//     //         if (adjacency.ContainsKey(i) && adjacency[i].Count > 0)
//     //         {
//     //             bool isLocalMax = adjacency[i].All(n => uvs[n].y <= uvs[i].y + 0.001f);
//     //             bool hasLowerNeighbor = adjacency[i].Any(n => uvs[n].y < uvs[i].y - 0.02f);
//     //             
//     //             if (isLocalMax && hasLowerNeighbor)
//     //             {
//     //                 rootVertices.Add(i);
//     //             }
//     //         }
//     //     }
//     //     
//     //     Debug.Log($"找到 {rootVertices.Count} 个根部顶点 (V值最大)");
//     //     
//     //     // 从根部构建毛发链
//     //     HashSet<int> visitedVertices = new HashSet<int>();
//     //     int stripIndex = 0;
//     //     
//     //     foreach (int rootVert in rootVertices)
//     //     {
//     //         if (visitedVertices.Contains(rootVert))
//     //             continue;
//     //         
//     //         HairStrip strip = new HairStrip { index = stripIndex };
//     //         HashSet<int> stripTriangles = new HashSet<int>();
//     //         
//     //         // BFS从根部向尖端追踪
//     //         Queue<int> queue = new Queue<int>();
//     //         queue.Enqueue(rootVert);
//     //         
//     //         while (queue.Count > 0)
//     //         {
//     //             int current = queue.Dequeue();
//     //             if (visitedVertices.Contains(current))
//     //                 continue;
//     //             
//     //             visitedVertices.Add(current);
//     //             strip.vertexIndices.Add(current);
//     //             
//     //             // 收集三角形
//     //             if (vertexToTriangles.ContainsKey(current))
//     //             {
//     //                 foreach (int triIdx in vertexToTriangles[current])
//     //                     stripTriangles.Add(triIdx);
//     //             }
//     //             
//     //             // 向V值更低的方向（尖端）追踪
//     //             float currentV = uvs[current].y;
//     //             foreach (int neighbor in adjacency[current])
//     //             {
//     //                 if (visitedVertices.Contains(neighbor))
//     //                     continue;
//     //                 
//     //                 float neighborV = uvs[neighbor].y;
//     //                 float deltaV = Mathf.Abs(neighborV - currentV);
//     //                 
//     //                 // 允许V值递减或小幅度增加（UV连续性）
//     //                 if (neighborV <= currentV + 0.02f && deltaV < uvContinuityThreshold)
//     //                 {
//     //                     queue.Enqueue(neighbor);
//     //                 }
//     //             }
//     //         }
//     //         
//     //         // 收集三角形
//     //         foreach (int triIdx in stripTriangles)
//     //         {
//     //             strip.triangleIndices.Add(triangles[triIdx * 3]);
//     //             strip.triangleIndices.Add(triangles[triIdx * 3 + 1]);
//     //             strip.triangleIndices.Add(triangles[triIdx * 3 + 2]);
//     //         }
//     //         
//     //         // 计算统计
//     //         if (strip.vertexIndices.Count >= 2)
//     //         {
//     //             strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//     //             strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//     //             
//     //             // ROOT = V值最大的点
//     //             int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//     //             // TIP = V值最小的点
//     //             int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//     //             
//     //             strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//     //             strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//     //             
//     //             hairStrips.Add(strip);
//     //             stripIndex++;
//     //         }
//     //     }
//     // }
//
//     /// <summary>
//     /// 基于UV分析（修复版 - 确保顶点和三角形对应）
//     /// </summary>
//     private void AnalyzeByUV()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         Vector3[] vertices = analyzedMesh.vertices;
//         int[] triangles = analyzedMesh.triangles;
//
//         if (uvs == null || uvs.Length == 0)
//         {
//             EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//             return;
//         }
//
//         var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//         var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//
//         // 找根部顶点（V值最大）
//         float globalMaxV = uvs.Max(uv => uv.y);
//         List<int> rootVertices = new List<int>();
//
//         for (int i = 0; i < uvs.Length; i++)
//         {
//             if (uvs[i].y >= globalMaxV - rootThreshold)
//             {
//                 rootVertices.Add(i);
//                 continue;
//             }
//
//             if (adjacency.ContainsKey(i) && adjacency[i].Count > 0)
//             {
//                 bool isLocalMax = adjacency[i].All(n => uvs[n].y <= uvs[i].y + 0.001f);
//                 bool hasLowerNeighbor = adjacency[i].Any(n => uvs[n].y < uvs[i].y - 0.02f);
//
//                 if (isLocalMax && hasLowerNeighbor)
//                 {
//                     rootVertices.Add(i);
//                 }
//             }
//         }
//
//         Debug.Log($"找到 {rootVertices.Count} 个根部顶点 (V值最大)");
//
//         HashSet<int> visitedVertices = new HashSet<int>();
//         int stripIndex = 0;
//
//         foreach (int rootVert in rootVertices)
//         {
//             if (visitedVertices.Contains(rootVert))
//                 continue;
//
//             HairStrip strip = new HairStrip { index = stripIndex };
//             HashSet<int> stripVertices = new HashSet<int>();
//             HashSet<int> stripTriangleIndices = new HashSet<int>(); // 存储三角形索引（第几个三角形）
//
//             Queue<int> queue = new Queue<int>();
//             queue.Enqueue(rootVert);
//
//             while (queue.Count > 0)
//             {
//                 int current = queue.Dequeue();
//                 if (visitedVertices.Contains(current))
//                     continue;
//
//                 visitedVertices.Add(current);
//                 stripVertices.Add(current);
//
//                 // 收集包含此顶点的三角形索引
//                 if (vertexToTriangles.ContainsKey(current))
//                 {
//                     foreach (int triIdx in vertexToTriangles[current])
//                     {
//                         stripTriangleIndices.Add(triIdx);
//                     }
//                 }
//
//                 float currentV = uvs[current].y;
//                 foreach (int neighbor in adjacency[current])
//                 {
//                     if (visitedVertices.Contains(neighbor))
//                         continue;
//
//                     float neighborV = uvs[neighbor].y;
//                     float deltaV = Mathf.Abs(neighborV - currentV);
//
//                     if (neighborV <= currentV + 0.02f && deltaV < uvContinuityThreshold)
//                     {
//                         queue.Enqueue(neighbor);
//                     }
//                 }
//             }
//
//             // 【关键修复】收集三角形时，确保所有相关顶点都被包含
//             foreach (int triIdx in stripTriangleIndices)
//             {
//                 int baseIdx = triIdx * 3;
//                 int v0 = triangles[baseIdx];
//                 int v1 = triangles[baseIdx + 1];
//                 int v2 = triangles[baseIdx + 2];
//
//                 // 检查这个三角形的所有顶点是否都在当前strip中
//                 // 如果三角形有顶点不在strip中，要么添加顶点，要么跳过这个三角形
//                 bool allInStrip = stripVertices.Contains(v0) &&
//                                   stripVertices.Contains(v1) &&
//                                   stripVertices.Contains(v2);
//
//                 if (allInStrip)
//                 {
//                     strip.triangleIndices.Add(v0);
//                     strip.triangleIndices.Add(v1);
//                     strip.triangleIndices.Add(v2);
//                 }
//                 else
//                 {
//                     // 选项1：添加缺失的顶点到strip
//                     // 这样可以保留更多三角形，但可能包含不属于这条毛发的顶点
//                     stripVertices.Add(v0);
//                     stripVertices.Add(v1);
//                     stripVertices.Add(v2);
//                     strip.triangleIndices.Add(v0);
//                     strip.triangleIndices.Add(v1);
//                     strip.triangleIndices.Add(v2);
//
//                     // 选项2：跳过这个三角形（注释掉上面的代码，取消下面的注释）
//                     // continue;
//                 }
//             }
//
//             // 使用收集到的完整顶点集
//             strip.vertexIndices = stripVertices.ToList();
//
//             // 计算统计
//             if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//
//                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//
//                 hairStrips.Add(strip);
//                 stripIndex++;
//             }
//         }
//
//         Debug.Log($"成功创建 {hairStrips.Count} 个有效毛发片");
//     }
//
//     /// <summary>
//     /// 基于连通分量分析
//     /// </summary>
//     private void AnalyzeByConnectedComponent()
//     {
//         int[] triangles = analyzedMesh.triangles;
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         // 构建边-三角形映射
//         var edgeTriangles = new Dictionary<Edge, List<int>>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIndex = i / 3;
//             AddEdgeTriangle(edgeTriangles, triangles[i], triangles[i + 1], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 1], triangles[i + 2], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 2], triangles[i], triIndex);
//         }
//         
//         // 并查集分组
//         int totalTriangles = triangles.Length / 3;
//         UnionFind uf = new UnionFind(totalTriangles);
//         
//         foreach (var kvp in edgeTriangles)
//         {
//             var tris = kvp.Value;
//             for (int i = 0; i < tris.Count - 1; i++)
//             {
//                 for (int j = i + 1; j < tris.Count; j++)
//                 {
//                     uf.Union(tris[i], tris[j]);
//                 }
//             }
//         }
//         
//         // 收集分组
//         var groups = new Dictionary<int, List<int>>();
//         for (int i = 0; i < totalTriangles; i++)
//         {
//             int root = uf.Find(i);
//             if (!groups.ContainsKey(root))
//                 groups[root] = new List<int>();
//             groups[root].Add(i);
//         }
//         
//         // 创建毛发片
//         int stripIndex = 0;
//         foreach (var group in groups.Values)
//         {
//             HairStrip strip = new HairStrip { index = stripIndex++ };
//             HashSet<int> vertSet = new HashSet<int>();
//             
//             foreach (int triIdx in group)
//             {
//                 int baseIdx = triIdx * 3;
//                 strip.triangleIndices.Add(triangles[baseIdx]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 1]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 2]);
//                 
//                 vertSet.Add(triangles[baseIdx]);
//                 vertSet.Add(triangles[baseIdx + 1]);
//                 vertSet.Add(triangles[baseIdx + 2]);
//             }
//             
//             strip.vertexIndices = vertSet.ToList();
//             
//             // 计算UV统计
//             if (uvs != null && uvs.Length > 0 && strip.vertexIndices.Count > 0)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//                 
//                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//                 
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//             }
//             
//             hairStrips.Add(strip);
//         }
//     }
//
//     /// <summary>
//     /// Scene视图绘制
//     /// </summary>
//     private void OnSceneGUI(SceneView sceneView)
//     {
//         if (!analysisComplete || targetObject == null || hairStrips.Count == 0 || analyzedMesh == null)
//             return;
//         
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         Transform transform = targetObject.transform;
//         
//         Handles.matrix = Matrix4x4.identity;
//         
//         if (showAllStrips)
//         {
//             foreach (var strip in hairStrips)
//             {
//                 float alpha = strip.index == currentStripIndex ? 1f : 0.2f;
//                 DrawStrip(strip, vertices, uvs, transform, alpha);
//             }
//         }
//         else if (currentStripIndex < hairStrips.Count)
//         {
//             DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
//         }
//     }
//
//     private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
//     {
//         Color stripColor = strip.debugColor;
//         
//         // 绘制三角形面
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawAAConvexPolygon(v0, v1, v2);
//         }
//         
//         // 绘制边
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.8f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawLine(v0, v1);
//             Handles.DrawLine(v1, v2);
//             Handles.DrawLine(v2, v0);
//         }
//         
//         // 绘制顶点（按V值着色：高V=绿色(根部)，低V=红色(尖端)）
//         foreach (int vertIdx in strip.vertexIndices)
//         {
//             Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
//             float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;
//             
//             // 归一化V值用于颜色
//             float normalizedV = strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0.5f;
//             
//             // 根部(V高)=绿色, 尖端(V低)=红色
//             Color vertColor = Color.Lerp(Color.red, Color.green, normalizedV);
//             vertColor.a = alpha;
//             
//             Handles.color = vertColor;
//             Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);
//             
//             // 标签
//             if ((showVertexLabels || showUVInfo) && alpha > 0.5f)
//             {
//                 string label = "";
//                 if (showVertexLabels) label += $"[{vertIdx}]";
//                 if (showUVInfo) label += $" V:{vValue:F3}";
//                 Handles.Label(worldPos + Vector3.up * vertexSphereSize * 1.5f, label, EditorStyles.miniLabel);
//             }
//         }
//         
//         // 绘制根部和尖端标记
//         if (showRootTipMarkers && alpha > 0.5f)
//         {
//             // ROOT标记 - 绿色大球
//             Handles.color = Color.green;
//             Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.rootPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"ROOT\nV={strip.maxV:F3}", EditorStyles.whiteBoldLabel);
//             
//             // TIP标记 - 红色大球
//             Handles.color = Color.red;
//             Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.tipPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"TIP\nV={strip.minV:F3}", EditorStyles.whiteBoldLabel);
//             
//             // 连接线
//             Handles.color = Color.yellow;
//             Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 3f);
//         }
//     }
//
//     private void FocusOnStrip(int index)
//     {
//         if (index >= hairStrips.Count) return;
//         
//         var strip = hairStrips[index];
//         Vector3 center = (strip.rootPosition + strip.tipPosition) / 2f;
//         float size = Mathf.Max(Vector3.Distance(strip.rootPosition, strip.tipPosition) * 3f, 0.1f);
//         
//         SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, size);
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 生成带UV差值的Mesh
//     /// </summary>
//     private void GenerateMeshWithUVDifference()
//     {
//         Mesh newMesh = Instantiate(analyzedMesh);
//         newMesh.name = analyzedMesh.name + "_WithUVDiff";
//         
//         Vector2[] uvs = newMesh.uv;
//         Color[] colors = new Color[newMesh.vertexCount];
//         
//         // 初始化
//         for (int i = 0; i < colors.Length; i++)
//             colors[i] = new Color(1, 1, 0, 1);
//         
//         // 计算每个顶点的差值
//         foreach (var strip in hairStrips)
//         {
//             foreach (int vertIdx in strip.vertexIndices)
//             {
//                 float v = uvs[vertIdx].y;
//                 
//                 // 归一化：根部(V最大)=1, 尖端(V最小)=0
//                 float diff = strip.vRange > 0.001f ? (v - strip.minV) / strip.vRange : 0f;
//                 
//                 colors[vertIdx].b = diff; // 存储到B通道
//             }
//         }
//         
//         newMesh.colors = colors;
//         
//         // 应用并保存
//         ApplyMesh(newMesh);
//         
//         string path = EditorUtility.SaveFilePanelInProject(
//             "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");
//         
//         if (!string.IsNullOrEmpty(path))
//         {
//             AssetDatabase.CreateAsset(newMesh, path);
//             AssetDatabase.SaveAssets();
//             Debug.Log($"✓ Mesh已保存: {path}");
//             Debug.Log("UV差值已存储到顶点颜色B通道 (根部=1, 尖端=0)");
//         }
//     }
//     
//     /// <summary>
//     /// 导出单个毛发片（带错误处理）
//     /// </summary>
//     private void ExportSingleStrip(HairStrip strip)
//     {
//         if (strip == null)
//         {
//             EditorUtility.DisplayDialog("错误", "毛发片数据为空", "确定");
//             return;
//         }
//     
//         // 验证数据
//         if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 顶点数不足 ({strip.vertexIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 三角形数不足 ({strip.triangleIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         try
//         {
//             Mesh mesh = CreateMeshFromStrip(strip);
//         
//             if (mesh == null || mesh.vertexCount == 0)
//             {
//                 EditorUtility.DisplayDialog("错误", "生成Mesh失败", "确定");
//                 return;
//             }
//         
//             string path = EditorUtility.SaveFilePanelInProject(
//                 "保存毛发片", 
//                 $"HairStrip_{strip.index}", 
//                 "asset", 
//                 "选择保存位置");
//         
//             if (!string.IsNullOrEmpty(path))
//             {
//                 // 检查是否已存在
//                 if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                 {
//                     AssetDatabase.DeleteAsset(path);
//                 }
//             
//                 AssetDatabase.CreateAsset(mesh, path);
//                 AssetDatabase.SaveAssets();
//             
//                 Debug.Log($"✓ 毛发片 #{strip.index} 已导出到: {path}");
//                 Debug.Log($"  顶点数: {mesh.vertexCount}, 三角形数: {mesh.triangles.Length / 3}");
//             }
//         }
//         catch (System.Exception e)
//         {
//             EditorUtility.DisplayDialog("导出失败", $"错误: {e.Message}", "确定");
//             Debug.LogError($"导出毛发片 #{strip.index} 失败: {e}");
//         }
//     }
//
//     // private void ExportSingleStrip(HairStrip strip)
//     // {
//     //     Mesh mesh = CreateMeshFromStrip(strip);
//     //     
//     //     string path = EditorUtility.SaveFilePanelInProject(
//     //         "保存毛发片", $"HairStrip_{strip.index}", "asset", "选择位置");
//     //     
//     //     if (!string.IsNullOrEmpty(path))
//     //     {
//     //         AssetDatabase.CreateAsset(mesh, path);
//     //         AssetDatabase.SaveAssets();
//     //         Debug.Log($"✓ 毛发片 #{strip.index} 已导出");
//     //     }
//     // }
//
//     /// <summary>
//     /// 导出所有毛发片（带错误处理）
//     /// </summary>
//     private void ExportAllStrips()
//     {
//         string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
//         if (string.IsNullOrEmpty(folder)) return;
//
//         // 转换为相对路径
//         if (folder.StartsWith(Application.dataPath))
//         {
//             folder = "Assets" + folder.Substring(Application.dataPath.Length);
//         }
//
//         // 确保文件夹存在
//         if (!AssetDatabase.IsValidFolder(folder))
//         {
//             Debug.LogError($"无效的文件夹路径: {folder}");
//             return;
//         }
//
//         int successCount = 0;
//         int failCount = 0;
//         List<string> failedStrips = new List<string>();
//
//         // 显示进度条
//         try
//         {
//             for (int i = 0; i < hairStrips.Count; i++)
//             {
//                 var strip = hairStrips[i];
//
//                 // 更新进度条
//                 bool cancel = EditorUtility.DisplayCancelableProgressBar(
//                     "导出毛发片",
//                     $"正在导出 {i + 1}/{hairStrips.Count}: HairStrip_{strip.index}",
//                     (float)i / hairStrips.Count);
//
//                 if (cancel)
//                 {
//                     Debug.Log("用户取消导出");
//                     break;
//                 }
//
//                 try
//                 {
//                     // 验证毛发片数据
//                     if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//                     {
//                         failedStrips.Add($"#{strip.index}: 顶点数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//                     {
//                         failedStrips.Add($"#{strip.index}: 三角形数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     Mesh mesh = CreateMeshFromStrip(strip);
//
//                     if (mesh != null && mesh.vertexCount > 0)
//                     {
//                         string path = $"{folder}/HairStrip_{strip.index}.asset";
//
//                         // 检查是否已存在同名资源
//                         if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                         {
//                             AssetDatabase.DeleteAsset(path);
//                         }
//
//                         AssetDatabase.CreateAsset(mesh, path);
//                         successCount++;
//                     }
//                     else
//                     {
//                         failedStrips.Add($"#{strip.index}: 生成Mesh失败");
//                         failCount++;
//                     }
//                 }
//                 catch (System.Exception e)
//                 {
//                     failedStrips.Add($"#{strip.index}: {e.Message}");
//                     failCount++;
//                     Debug.LogError($"导出毛发片 #{strip.index} 失败: {e.Message}");
//                 }
//             }
//         }
//         finally
//         {
//             EditorUtility.ClearProgressBar();
//         }
//
//         AssetDatabase.SaveAssets();
//         AssetDatabase.Refresh();
//
//         // 显示结果
//         string message = $"导出完成！\n成功: {successCount}\n失败: {failCount}";
//
//         if (failedStrips.Count > 0)
//         {
//             message += $"\n\n失败详情:\n{string.Join("\n", failedStrips.Take(10))}";
//             if (failedStrips.Count > 10)
//             {
//                 message += $"\n... 还有 {failedStrips.Count - 10} 个";
//             }
//         }
//
//         EditorUtility.DisplayDialog("导出结果", message, "确定");
//
//         Debug.Log($"✓ 毛发片导出完成: 成功 {successCount}, 失败 {failCount}, 保存到 {folder}");
//     }
//
//     // private void ExportAllStrips()
//     // {
//     //     string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
//     //     if (string.IsNullOrEmpty(folder)) return;
//     //     
//     //     if (folder.StartsWith(Application.dataPath))
//     //         folder = "Assets" + folder.Substring(Application.dataPath.Length);
//     //     
//     //     foreach (var strip in hairStrips)
//     //     {
//     //         Mesh mesh = CreateMeshFromStrip(strip);
//     //         AssetDatabase.CreateAsset(mesh, $"{folder}/HairStrip_{strip.index}.asset");
//     //     }
//     //     
//     //     AssetDatabase.SaveAssets();
//     //     Debug.Log($"✓ 已导出 {hairStrips.Count} 个毛发片到 {folder}");
//     // }
//
//     private void ExportAnalysisReport()
//     {
//         string path = EditorUtility.SaveFilePanel("保存分析报告", "", "HairAnalysisReport", "txt");
//         if (string.IsNullOrEmpty(path)) return;
//         
//         var sb = new System.Text.StringBuilder();
//         sb.AppendLine("========== 毛发分析报告 ==========");
//         sb.AppendLine($"物体: {targetObject.name}");
//         sb.AppendLine($"Mesh: {analyzedMesh.name}");
//         sb.AppendLine($"总顶点数: {analyzedMesh.vertexCount}");
//         sb.AppendLine($"总三角形数: {analyzedMesh.triangles.Length / 3}");
//         sb.AppendLine($"识别毛发片数: {hairStrips.Count}");
//         sb.AppendLine();
//         sb.AppendLine("UV规则: ROOT(根部)=V值最大, TIP(尖端)=V值最小");
//         sb.AppendLine();
//         sb.AppendLine("---------- 各毛发片详情 ----------");
//         
//         foreach (var strip in hairStrips)
//         {
//             sb.AppendLine($"\n毛发片 #{strip.index}:");
//             sb.AppendLine($"  顶点数: {strip.vertexCount}");
//             sb.AppendLine($"  三角形数: {strip.triangleCount}");
//             sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4}");
//             sb.AppendLine($"  V值跨度: {strip.vRange:F4}");
//             sb.AppendLine($"  顶点索引: {string.Join(",", strip.vertexIndices.Take(30))}{(strip.vertexIndices.Count > 30 ? "..." : "")}");
//         }
//         
//         System.IO.File.WriteAllText(path, sb.ToString());
//         Debug.Log($"✓ 报告已保存: {path}");
//     }
//
//     /// <summary>
//     /// 从毛发片创建独立Mesh（修复版）
//     /// </summary>
//     private Mesh CreateMeshFromStrip(HairStrip strip)
//     {
//         Vector3[] origVerts = analyzedMesh.vertices;
//         Vector2[] origUVs = analyzedMesh.uv;
//         Vector3[] origNormals = analyzedMesh.normals;
//         Color[] origColors = analyzedMesh.colors;
//
//         // 首先，确保收集所有三角形引用的顶点
//         HashSet<int> allVertices = new HashSet<int>(strip.vertexIndices);
//
//         // 检查三角形中是否有遗漏的顶点
//         for (int i = 0; i < strip.triangleIndices.Count; i++)
//         {
//             int vertIdx = strip.triangleIndices[i];
//             if (!allVertices.Contains(vertIdx))
//             {
//                 allVertices.Add(vertIdx);
//                 Debug.LogWarning($"毛发片 #{strip.index}: 三角形引用了未在顶点列表中的顶点 {vertIdx}，已自动添加");
//             }
//         }
//
//         // 使用完整的顶点列表
//         List<int> finalVertexList = allVertices.ToList();
//
//         // 建立旧索引到新索引的映射
//         Dictionary<int, int> remap = new Dictionary<int, int>();
//         for (int i = 0; i < finalVertexList.Count; i++)
//         {
//             remap[finalVertexList[i]] = i;
//         }
//
//         // 创建新的顶点数据
//         int vertCount = finalVertexList.Count;
//         Vector3[] newVerts = new Vector3[vertCount];
//         Vector2[] newUVs = new Vector2[vertCount];
//         Vector3[] newNormals = new Vector3[vertCount];
//         Color[] newColors = new Color[vertCount];
//
//         for (int i = 0; i < vertCount; i++)
//         {
//             int origIdx = finalVertexList[i];
//
//             newVerts[i] = origVerts[origIdx];
//
//             newUVs[i] = (origUVs != null && origIdx < origUVs.Length)
//                 ? origUVs[origIdx]
//                 : Vector2.zero;
//
//             newNormals[i] = (origNormals != null && origIdx < origNormals.Length)
//                 ? origNormals[origIdx]
//                 : Vector3.up;
//
//             newColors[i] = (origColors != null && origIdx < origColors.Length)
//                 ? origColors[origIdx]
//                 : Color.white;
//         }
//
//         // 重映射三角形索引
//         List<int> newTriangles = new List<int>();
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             // 确保三角形的三个顶点都存在
//             if (i + 2 < strip.triangleIndices.Count)
//             {
//                 int idx0 = strip.triangleIndices[i];
//                 int idx1 = strip.triangleIndices[i + 1];
//                 int idx2 = strip.triangleIndices[i + 2];
//
//                 if (remap.ContainsKey(idx0) && remap.ContainsKey(idx1) && remap.ContainsKey(idx2))
//                 {
//                     newTriangles.Add(remap[idx0]);
//                     newTriangles.Add(remap[idx1]);
//                     newTriangles.Add(remap[idx2]);
//                 }
//                 else
//                 {
//                     Debug.LogWarning($"毛发片 #{strip.index}: 跳过无效三角形 ({idx0}, {idx1}, {idx2})");
//                 }
//             }
//         }
//
//         // 计算UV差值并存储到顶点颜色B通道
//         float minV = float.MaxValue;
//         float maxV = float.MinValue;
//
//         // 先找出V值范围
//         for (int i = 0; i < vertCount; i++)
//         {
//             float v = newUVs[i].y;
//             if (v < minV) minV = v;
//             if (v > maxV) maxV = v;
//         }
//
//         float vRange = maxV - minV;
//
//         // 计算每个顶点的差值
//         for (int i = 0; i < vertCount; i++)
//         {
//             float v = newUVs[i].y;
//             // 根部(V最大)=1, 尖端(V最小)=0
//             float diff = vRange > 0.001f ? (v - minV) / vRange : 0f;
//             newColors[i].b = diff;
//         }
//
//         // 创建Mesh
//         Mesh mesh = new Mesh();
//         mesh.name = $"HairStrip_{strip.index}";
//         mesh.vertices = newVerts;
//         mesh.uv = newUVs;
//         mesh.normals = newNormals;
//         mesh.colors = newColors;
//
//         if (newTriangles.Count >= 3)
//         {
//             mesh.triangles = newTriangles.ToArray();
//         }
//         else
//         {
//             Debug.LogWarning($"毛发片 #{strip.index}: 三角形数量不足 ({newTriangles.Count / 3})");
//         }
//
//         mesh.RecalculateBounds();
//
//         return mesh;
//     }
//     // private Mesh CreateMeshFromStrip(HairStrip strip)
//     // {
//     //     Vector3[] origVerts = analyzedMesh.vertices;
//     //     Vector2[] origUVs = analyzedMesh.uv;
//     //     Vector3[] origNormals = analyzedMesh.normals;
//     //     
//     //     // 重映射
//     //     var remap = new Dictionary<int, int>();
//     //     for (int i = 0; i < strip.vertexIndices.Count; i++)
//     //         remap[strip.vertexIndices[i]] = i;
//     //     
//     //     Vector3[] newVerts = strip.vertexIndices.Select(v => origVerts[v]).ToArray();
//     //     Vector2[] newUVs = strip.vertexIndices.Select(v => origUVs != null && v < origUVs.Length ? origUVs[v] : Vector2.zero).ToArray();
//     //     Vector3[] newNormals = strip.vertexIndices.Select(v => origNormals != null && v < origNormals.Length ? origNormals[v] : Vector3.up).ToArray();
//     //     
//     //     int[] newTris = new int[strip.triangleIndices.Count];
//     //     for (int i = 0; i < strip.triangleIndices.Count; i++)
//     //         newTris[i] = remap[strip.triangleIndices[i]];
//     //     
//     //     // 计算顶点色（UV差值）
//     //     Color[] newColors = new Color[newVerts.Length];
//     //     for (int i = 0; i < strip.vertexIndices.Count; i++)
//     //     {
//     //         float v = newUVs[i].y;
//     //         float diff = strip.vRange > 0.001f ? (v - strip.minV) / strip.vRange : 0f;
//     //         newColors[i] = new Color(1, 1, diff, 1);
//     //     }
//     //     
//     //     Mesh mesh = new Mesh
//     //     {
//     //         name = $"HairStrip_{strip.index}",
//     //         vertices = newVerts,
//     //         uv = newUVs,
//     //         normals = newNormals,
//     //         colors = newColors,
//     //         triangles = newTris
//     //     };
//     //     mesh.RecalculateBounds();
//     //     
//     //     return mesh;
//     // }
//
//     #region Helper Methods
//     
//     private Mesh GetMesh()
//     {
//         if (targetObject == null) return null;
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         return mf?.sharedMesh ?? smr?.sharedMesh;
//     }
//     
//     private void ApplyMesh(Mesh mesh)
//     {
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         if (mf != null) mf.sharedMesh = mesh;
//         else if (smr != null) smr.sharedMesh = mesh;
//     }
//     
//     private Dictionary<int, HashSet<int>> BuildAdjacencyList(int[] triangles, int vertexCount)
//     {
//         var adj = new Dictionary<int, HashSet<int>>();
//         for (int i = 0; i < vertexCount; i++) adj[i] = new HashSet<int>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
//             adj[v0].Add(v1); adj[v0].Add(v2);
//             adj[v1].Add(v0); adj[v1].Add(v2);
//             adj[v2].Add(v0); adj[v2].Add(v1);
//         }
//         return adj;
//     }
//     
//     private Dictionary<int, List<int>> BuildVertexToTrianglesMap(int[] triangles)
//     {
//         var map = new Dictionary<int, List<int>>();
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIdx = i / 3;
//             for (int j = 0; j < 3; j++)
//             {
//                 int v = triangles[i + j];
//                 if (!map.ContainsKey(v)) map[v] = new List<int>();
//                 map[v].Add(triIdx);
//             }
//         }
//         return map;
//     }
//     
//     private void AddEdgeTriangle(Dictionary<Edge, List<int>> dict, int v0, int v1, int triIndex)
//     {
//         Edge edge = new Edge(v0, v1);
//         if (!dict.ContainsKey(edge)) dict[edge] = new List<int>();
//         dict[edge].Add(triIndex);
//     }
//     
//     public struct Edge : System.IEquatable<Edge>
//     {
//         public int v0, v1;
//         public Edge(int a, int b) { v0 = Mathf.Min(a, b); v1 = Mathf.Max(a, b); }
//         public bool Equals(Edge other) => v0 == other.v0 && v1 == other.v1;
//         public override int GetHashCode() => v0 ^ (v1 << 16);
//     }
//     
//     public class UnionFind
//     {
//         private int[] parent, rank;
//         public UnionFind(int n)
//         {
//             parent = new int[n]; rank = new int[n];
//             for (int i = 0; i < n; i++) parent[i] = i;
//         }
//         public int Find(int x) { if (parent[x] != x) parent[x] = Find(parent[x]); return parent[x]; }
//         public void Union(int x, int y)
//         {
//             int px = Find(x), py = Find(y);
//             if (px == py) return;
//             if (rank[px] < rank[py]) parent[px] = py;
//             else if (rank[px] > rank[py]) parent[py] = px;
//             else { parent[py] = px; rank[px]++; }
//         }
//     }
//     
//     #endregion
// }
//---------------------------以下增加了全局uv模式，之前是单根自己内部（适合不连续）-----------------------------
// using UnityEngine;
// using UnityEditor;
// using System.Collections.Generic;
// using System.Linq;
//
// public class HairAnalyzerVisualizer : EditorWindow
// {
//     private GameObject targetObject;
//     private Mesh analyzedMesh;
//     
//     // 分析结果
//     private List<HairStrip> hairStrips = new List<HairStrip>();
//     private int currentStripIndex = 0;
//     
//     // 全局UV统计
//     private float globalMinV = 0f;
//     private float globalMaxV = 1f;
//     private float globalVRange = 1f;
//     
//     // 可视化设置
//     private bool showAllStrips = true;
//     private bool showVertexLabels = false;
//     private bool showUVInfo = true;
//     private bool showRootTipMarkers = true;
//     private float vertexSphereSize = 0.002f;
//     
//     // 分析参数
//     private float rootThreshold = 0.05f;
//     private float uvContinuityThreshold = 0.3f;
//     private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
//     
//     // 【新增】UV差值计算模式
//     private UVDifferenceMode uvDifferenceMode = UVDifferenceMode.PerStrip;
//     
//     private Vector2 scrollPos;
//     private bool analysisComplete = false;
//     
//     public enum AnalysisMethod
//     {
//         UVBased,
//         TriangleStrip,
//         ConnectedComponent
//     }
//     
//     /// <summary>
//     /// UV差值计算模式
//     /// </summary>
//     public enum UVDifferenceMode
//     {
//         [InspectorName("单片独立计算")]
//         PerStrip,           // 每个毛发片独立计算（原有模式）
//         [InspectorName("全局V值计算")]
//         GlobalV,            // 使用全局最大V值计算
//         [InspectorName("全局范围归一化")]
//         GlobalRange         // 使用全局V范围归一化
//     }
//
//     /// <summary>
//     /// 毛发条带数据
//     /// </summary>
//     public class HairStrip
//     {
//         public int index;
//         public List<int> vertexIndices = new List<int>();
//         public List<int> triangleIndices = new List<int>();
//         public Color debugColor;
//         
//         // UV统计 - 注意：maxV是根部，minV是尖端
//         public float minV; // 尖端（TIP）
//         public float maxV; // 根部（ROOT）
//         
//         public Vector3 rootPosition; // V值最大的点
//         public Vector3 tipPosition;  // V值最小的点
//         
//         public int vertexCount => vertexIndices.Count;
//         public int triangleCount => triangleIndices.Count / 3;
//         public float vRange => maxV - minV;
//     }
//
//     [MenuItem("Tools/Hair/Hair Analyzer Visualizer")]
//     public static void ShowWindow()
//     {
//         var window = GetWindow<HairAnalyzerVisualizer>("毛发分析可视化");
//         window.minSize = new Vector2(420, 750);
//     }
//
//     private void OnEnable()
//     {
//         SceneView.duringSceneGui += OnSceneGUI;
//     }
//
//     private void OnDisable()
//     {
//         SceneView.duringSceneGui -= OnSceneGUI;
//     }
//
//     private void OnGUI()
//     {
//         scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
//         
//         DrawHeader();
//         DrawInputSection();
//         DrawAnalysisSettings();
//         DrawAnalysisButtons();
//         
//         if (analysisComplete)
//         {
//             DrawResultsSection();
//             DrawStripNavigator();
//             DrawVisualizationSettings();
//             DrawExportSection();
//         }
//         
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void DrawHeader()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
//         {
//             fontSize = 16,
//             alignment = TextAnchor.MiddleCenter
//         };
//         GUILayout.Label("🔍 毛发结构分析与可视化", titleStyle);
//         
//         EditorGUILayout.Space(5);
//         
//         EditorGUILayout.HelpBox(
//             "UV规则：\n" +
//             "• ROOT（根部）= V值最大 → 显示为绿色\n" +
//             "• TIP（尖端）= V值最小 → 显示为红色\n" +
//             "• 差值结果：根部=1，尖端=0", 
//             MessageType.Info);
//         
//         EditorGUILayout.Space(10);
//     }
//
//     private void DrawInputSection()
//     {
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📥 输入", EditorStyles.boldLabel);
//         
//         EditorGUI.BeginChangeCheck();
//         targetObject = (GameObject)EditorGUILayout.ObjectField(
//             "目标物体", targetObject, typeof(GameObject), true);
//         if (EditorGUI.EndChangeCheck())
//         {
//             analysisComplete = false;
//             hairStrips.Clear();
//         }
//         
//         if (targetObject != null)
//         {
//             Mesh mesh = GetMesh();
//             if (mesh != null)
//             {
//                 EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
//                 EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
//                 
//                 if (mesh.uv != null && mesh.uv.Length > 0)
//                 {
//                     float minV = mesh.uv.Min(uv => uv.y);
//                     float maxV = mesh.uv.Max(uv => uv.y);
//                     EditorGUILayout.LabelField("UV V值范围", $"{minV:F3} ~ {maxV:F3}");
//                 }
//                 else
//                 {
//                     EditorGUILayout.HelpBox("警告：Mesh没有UV数据！", MessageType.Warning);
//                 }
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("⚙️ 分析设置", EditorStyles.boldLabel);
//         
//         analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
//         
//         string methodDesc = "";
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 methodDesc = "从V值最大的点(根部)出发，沿V递减方向追踪";
//                 break;
//             case AnalysisMethod.TriangleStrip:
//                 methodDesc = "通过共享边的三角形分组";
//                 break;
//             case AnalysisMethod.ConnectedComponent:
//                 methodDesc = "完全独立的三角形组为一片";
//                 break;
//         }
//         EditorGUILayout.HelpBox(methodDesc, MessageType.None);
//         
//         rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
//         uvContinuityThreshold = EditorGUILayout.Slider("UV连续性阈值", uvContinuityThreshold, 0.1f, 0.5f);
//         
//         EditorGUILayout.Space(5);
//         EditorGUILayout.LabelField("UV差值计算", EditorStyles.boldLabel);
//         
//         uvDifferenceMode = (UVDifferenceMode)EditorGUILayout.EnumPopup("计算模式", uvDifferenceMode);
//         
//         // 显示模式说明
//         string modeDesc = "";
//         switch (uvDifferenceMode)
//         {
//             // case UVDifferenceMode.PerStrip:
//             //     modeDesc = "每片毛发独立归一化\ndiff = (V - 片内minV) / 片内vRange\n不同毛发片的根部都是1";
//             //     break;
//             // case UVDifferenceMode.GlobalV:
//             //     modeDesc = "使用全局最大V作为根部基准\ndiff = (V - 片内minV) / (全局maxV - 片内minV)\n所有毛发在同一UV空间下计算";
//             //     break;
//             // case UVDifferenceMode.GlobalRange:
//             //     modeDesc = "使用全局V范围归一化\ndiff = (V - 全局minV) / 全局vRange\n完全统一的归一化";
//             //     break;
//             case UVDifferenceMode.PerStrip:
//                 modeDesc = "每片毛发独立归一化\ndiff = (V - 片内minV) / 片内vRange\n根部=1, 尖端=0";
//                 break;
//             case UVDifferenceMode.GlobalV:
//                 modeDesc = "统一根部起点（全局maxV）\ndiff = (全局maxV - V) / (全局maxV - 片内minV)\n根部=0, 尖端=1";
//                 break;
//             case UVDifferenceMode.GlobalRange:
//                 modeDesc = "使用全局V范围归一化\ndiff = (全局maxV - V) / 全局vRange\n根部=1, 尖端=0";
//                 break;
//         }
//         EditorGUILayout.HelpBox(modeDesc, MessageType.None);
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisButtons()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUI.enabled = targetObject != null && GetMesh() != null;
//         
//         GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
//         if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
//         {
//             PerformAnalysis();
//         }
//         GUI.backgroundColor = Color.white;
//         
//         GUI.enabled = true;
//     }
//
//     private void DrawResultsSection()
//     {
//         EditorGUILayout.Space(10);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
//         
//         EditorGUILayout.LabelField("识别到的毛发片", hairStrips.Count.ToString());
//         
//         // 显示全局UV统计
//         EditorGUILayout.Space(3);
//         EditorGUILayout.LabelField("全局UV统计", EditorStyles.boldLabel);
//         EditorGUILayout.BeginHorizontal();
//         EditorGUILayout.LabelField($"全局 Min V: {globalMinV:F4}", GUILayout.Width(150));
//         EditorGUILayout.LabelField($"全局 Max V: {globalMaxV:F4}");
//         EditorGUILayout.EndHorizontal();
//         EditorGUILayout.LabelField($"全局 V Range: {globalVRange:F4}");
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.Space(3);
//             var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
//             var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
//             var vRanges = hairStrips.Select(s => s.vRange).ToList();
//             
//             EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} ~ {vertexCounts.Max()} (平均:{vertexCounts.Average():F1})");
//             EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} ~ {triCounts.Max()}");
//             EditorGUILayout.LabelField("单片V值跨度范围", $"{vRanges.Min():F3} ~ {vRanges.Max():F3}");
//             
//             // 检测异常
//             int tooSmall = hairStrips.Count(s => s.vertexCount < 3);
//             int tooLarge = hairStrips.Count(s => s.vertexCount > 50);
//             int noVRange = hairStrips.Count(s => s.vRange < 0.01f);
//             
//             if (tooSmall > 0 || tooLarge > 0 || noVRange > 0)
//             {
//                 string warning = "检测到异常：\n";
//                 if (tooSmall > 0) warning += $"• {tooSmall} 片顶点数过少(<3)\n";
//                 if (tooLarge > 0) warning += $"• {tooLarge} 片顶点数过多(>50)\n";
//                 if (noVRange > 0) warning += $"• {noVRange} 片V值跨度过小(<0.01)";
//                 EditorGUILayout.HelpBox(warning, MessageType.Warning);
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawStripNavigator()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.BeginHorizontal();
//             
//             if (GUILayout.Button("◀", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
//             
//             if (GUILayout.Button("▶", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             EditorGUILayout.EndHorizontal();
//             
//             // 当前毛发片详情
//             if (currentStripIndex < hairStrips.Count)
//             {
//                 var strip = hairStrips[currentStripIndex];
//                 
//                 EditorGUILayout.Space(5);
//                 EditorGUILayout.BeginVertical("helpbox");
//                 
//                 EditorGUILayout.LabelField($"毛发片 #{strip.index}", EditorStyles.boldLabel);
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString(), GUILayout.Width(150));
//                 EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("根部V值(MAX)", $"{strip.maxV:F4}", GUILayout.Width(150));
//                 EditorGUILayout.LabelField("尖端V值(MIN)", $"{strip.minV:F4}");
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F4}");
//                 
//                 // 显示当前模式下的差值计算预览
//                 float rootDiff = CalculateUVDifference(strip.maxV, strip);
//                 float tipDiff = CalculateUVDifference(strip.minV, strip);
//                 EditorGUILayout.LabelField($"差值预览 ({uvDifferenceMode})", $"根部={rootDiff:F3}, 尖端={tipDiff:F3}");
//                 
//                 // 顶点列表预览
//                 string vertPreview = string.Join(", ", strip.vertexIndices.Take(15));
//                 if (strip.vertexIndices.Count > 15) vertPreview += "...";
//                 EditorGUILayout.LabelField("顶点:", vertPreview, EditorStyles.miniLabel);
//                 
//                 EditorGUILayout.EndVertical();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 if (GUILayout.Button("聚焦此片"))
//                 {
//                     FocusOnStrip(currentStripIndex);
//                 }
//                 if (GUILayout.Button("导出此片"))
//                 {
//                     ExportSingleStrip(strip);
//                 }
//                 EditorGUILayout.EndHorizontal();
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawVisualizationSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
//         
//         showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
//         showVertexLabels = EditorGUILayout.Toggle("显示顶点索引", showVertexLabels);
//         showUVInfo = EditorGUILayout.Toggle("显示UV V值", showUVInfo);
//         showRootTipMarkers = EditorGUILayout.Toggle("显示根部/尖端标记", showRootTipMarkers);
//         vertexSphereSize = EditorGUILayout.Slider("顶点大小", vertexSphereSize, 0.0005f, 0.02f);
//         
//         EditorGUILayout.BeginHorizontal();
//         if (GUILayout.Button("刷新视图"))
//         {
//             SceneView.RepaintAll();
//         }
//         if (GUILayout.Button("重置相机"))
//         {
//             if (targetObject != null)
//             {
//                 SceneView.lastActiveSceneView?.LookAt(targetObject.transform.position);
//             }
//         }
//         EditorGUILayout.EndHorizontal();
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawExportSection()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📤 导出", EditorStyles.boldLabel);
//         
//         // 显示当前使用的UV差值模式
//         EditorGUILayout.LabelField($"当前UV差值模式: {uvDifferenceMode}", EditorStyles.miniLabel);
//         
//         if (GUILayout.Button("生成带UV差值的Mesh"))
//         {
//             GenerateMeshWithUVDifference();
//         }
//         
//         if (GUILayout.Button("导出所有毛发片"))
//         {
//             ExportAllStrips();
//         }
//         
//         if (GUILayout.Button("导出分析报告"))
//         {
//             ExportAnalysisReport();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 根据当前模式计算UV差值
//     /// </summary>
//     private float CalculateUVDifference(float vValue, HairStrip strip)
//     {
//         // switch (uvDifferenceMode)
//         // {
//         //     case UVDifferenceMode.PerStrip:
//         //         // 每片独立计算：(V - 片内minV) / 片内vRange
//         //         return strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0f;
//         //         
//         //     case UVDifferenceMode.GlobalV:
//         //         // 全局V计算：使用全局maxV作为根部基准
//         //         // diff = (V - 片内minV) / (全局maxV - 片内minV)
//         //         float rangeToGlobalMax = globalMaxV - strip.minV;
//         //         return rangeToGlobalMax > 0.001f ? (vValue - strip.minV) / rangeToGlobalMax : 0f;
//         //         
//         //     case UVDifferenceMode.GlobalRange:
//         //         // 全局范围归一化：(V - 全局minV) / 全局vRange
//         //         return globalVRange > 0.001f ? (vValue - globalMinV) / globalVRange : 0f;
//         //         
//         //     default:
//         //         return 0f;
//         // }
//         switch (uvDifferenceMode)
//         {
//             case UVDifferenceMode.PerStrip:
//                 // 每片独立计算：(V - 片内minV) / 片内vRange
//                 // 根部(maxV)=1, 尖端(minV)=0
//                 return strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0f;
//             
//             case UVDifferenceMode.GlobalV:
//                 // 全局V计算：统一根部起点
//                 // diff = (全局maxV - V) / (全局maxV - 片内minV)
//                 // 根部(全局maxV)=0, 尖端(片内minV)=1
//                 float rangeFromGlobalMax = globalMaxV - strip.minV;
//                 return rangeFromGlobalMax > 0.001f ? (globalMaxV - vValue) / rangeFromGlobalMax : 0f;
//             
//             case UVDifferenceMode.GlobalRange:
//                 // 全局范围归一化：(全局MaxV - 片MaxV) / 全局vRange  
//                 // 根部(全局maxV)=1, 尖端(全局minV)=0
//                 return globalMaxV;//(globalMaxV - strip.maxV);
//                 //return globalVRange > 0.001f ? (globalMaxV - vValue) / globalVRange : 0f;
//             
//             default:
//                 return 0f;
//         }
//     }
//
//     /// <summary>
//     /// 执行分析
//     /// </summary>
//     private void PerformAnalysis()
//     {
//         analyzedMesh = GetMesh();
//         if (analyzedMesh == null) return;
//         
//         hairStrips.Clear();
//         
//         // 先计算全局UV统计
//         CalculateGlobalUVStats();
//         
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 AnalyzeByUV();
//                 break;
//             case AnalysisMethod.TriangleStrip:
//             case AnalysisMethod.ConnectedComponent:
//                 AnalyzeByConnectedComponent();
//                 break;
//         }
//         
//         // 分配随机颜色
//         System.Random rand = new System.Random(42);
//         foreach (var strip in hairStrips)
//         {
//             strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
//         }
//         
//         analysisComplete = true;
//         currentStripIndex = 0;
//         
//         Debug.Log($"✓ 分析完成！识别到 {hairStrips.Count} 个毛发片");
//         Debug.Log($"  全局UV范围: V = {globalMinV:F4} ~ {globalMaxV:F4}, Range = {globalVRange:F4}");
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 计算全局UV统计
//     /// </summary>
//     private void CalculateGlobalUVStats()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         if (uvs == null || uvs.Length == 0)
//         {
//             globalMinV = 0f;
//             globalMaxV = 1f;
//             globalVRange = 1f;
//             return;
//         }
//         
//         globalMinV = float.MaxValue;
//         globalMaxV = float.MinValue;
//         
//         foreach (var uv in uvs)
//         {
//             if (uv.y < globalMinV) globalMinV = uv.y;
//             if (uv.y > globalMaxV) globalMaxV = uv.y;
//         }
//         
//         globalVRange = globalMaxV - globalMinV;
//         
//         // 防止除零
//         if (globalVRange < 0.001f)
//         {
//             globalVRange = 1f;
//         }
//     }
//
//     /// <summary>
//     /// 基于UV分析（修复版 - 确保顶点和三角形对应）
//     /// </summary>
//     private void AnalyzeByUV()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         Vector3[] vertices = analyzedMesh.vertices;
//         int[] triangles = analyzedMesh.triangles;
//
//         if (uvs == null || uvs.Length == 0)
//         {
//             EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//             return;
//         }
//
//         var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//         var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//
//         // 找根部顶点（V值最大）
//         List<int> rootVertices = new List<int>();
//
//         for (int i = 0; i < uvs.Length; i++)
//         {
//             if (uvs[i].y >= globalMaxV - rootThreshold)
//             {
//                 rootVertices.Add(i);
//                 continue;
//             }
//
//             if (adjacency.ContainsKey(i) && adjacency[i].Count > 0)
//             {
//                 bool isLocalMax = adjacency[i].All(n => uvs[n].y <= uvs[i].y + 0.001f);
//                 bool hasLowerNeighbor = adjacency[i].Any(n => uvs[n].y < uvs[i].y - 0.02f);
//
//                 if (isLocalMax && hasLowerNeighbor)
//                 {
//                     rootVertices.Add(i);
//                 }
//             }
//         }
//
//         Debug.Log($"找到 {rootVertices.Count} 个根部顶点 (V值最大，全局Max={globalMaxV:F4})");
//
//         HashSet<int> visitedVertices = new HashSet<int>();
//         int stripIndex = 0;
//
//         foreach (int rootVert in rootVertices)
//         {
//             if (visitedVertices.Contains(rootVert))
//                 continue;
//
//             HairStrip strip = new HairStrip { index = stripIndex };
//             HashSet<int> stripVertices = new HashSet<int>();
//             HashSet<int> stripTriangleIndices = new HashSet<int>();
//
//             Queue<int> queue = new Queue<int>();
//             queue.Enqueue(rootVert);
//
//             while (queue.Count > 0)
//             {
//                 int current = queue.Dequeue();
//                 if (visitedVertices.Contains(current))
//                     continue;
//
//                 visitedVertices.Add(current);
//                 stripVertices.Add(current);
//
//                 if (vertexToTriangles.ContainsKey(current))
//                 {
//                     foreach (int triIdx in vertexToTriangles[current])
//                     {
//                         stripTriangleIndices.Add(triIdx);
//                     }
//                 }
//
//                 float currentV = uvs[current].y;
//                 foreach (int neighbor in adjacency[current])
//                 {
//                     if (visitedVertices.Contains(neighbor))
//                         continue;
//
//                     float neighborV = uvs[neighbor].y;
//                     float deltaV = Mathf.Abs(neighborV - currentV);
//
//                     if (neighborV <= currentV + 0.02f && deltaV < uvContinuityThreshold)
//                     {
//                         queue.Enqueue(neighbor);
//                     }
//                 }
//             }
//
//             foreach (int triIdx in stripTriangleIndices)
//             {
//                 int baseIdx = triIdx * 3;
//                 int v0 = triangles[baseIdx];
//                 int v1 = triangles[baseIdx + 1];
//                 int v2 = triangles[baseIdx + 2];
//
//                 bool allInStrip = stripVertices.Contains(v0) &&
//                                   stripVertices.Contains(v1) &&
//                                   stripVertices.Contains(v2);
//
//                 if (allInStrip)
//                 {
//                     strip.triangleIndices.Add(v0);
//                     strip.triangleIndices.Add(v1);
//                     strip.triangleIndices.Add(v2);
//                 }
//                 else
//                 {
//                     stripVertices.Add(v0);
//                     stripVertices.Add(v1);
//                     stripVertices.Add(v2);
//                     strip.triangleIndices.Add(v0);
//                     strip.triangleIndices.Add(v1);
//                     strip.triangleIndices.Add(v2);
//                 }
//             }
//
//             strip.vertexIndices = stripVertices.ToList();
//
//             if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//
//                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//
//                 hairStrips.Add(strip);
//                 stripIndex++;
//             }
//         }
//
//         Debug.Log($"成功创建 {hairStrips.Count} 个有效毛发片");
//     }
//
//     /// <summary>
//     /// 基于连通分量分析
//     /// </summary>
//     private void AnalyzeByConnectedComponent()
//     {
//         int[] triangles = analyzedMesh.triangles;
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         var edgeTriangles = new Dictionary<Edge, List<int>>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIndex = i / 3;
//             AddEdgeTriangle(edgeTriangles, triangles[i], triangles[i + 1], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 1], triangles[i + 2], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 2], triangles[i], triIndex);
//         }
//         
//         int totalTriangles = triangles.Length / 3;
//         UnionFind uf = new UnionFind(totalTriangles);
//         
//         foreach (var kvp in edgeTriangles)
//         {
//             var tris = kvp.Value;
//             for (int i = 0; i < tris.Count - 1; i++)
//             {
//                 for (int j = i + 1; j < tris.Count; j++)
//                 {
//                     uf.Union(tris[i], tris[j]);
//                 }
//             }
//         }
//         
//         var groups = new Dictionary<int, List<int>>();
//         for (int i = 0; i < totalTriangles; i++)
//         {
//             int root = uf.Find(i);
//             if (!groups.ContainsKey(root))
//                 groups[root] = new List<int>();
//             groups[root].Add(i);
//         }
//         
//         int stripIndex = 0;
//         foreach (var group in groups.Values)
//         {
//             HairStrip strip = new HairStrip { index = stripIndex++ };
//             HashSet<int> vertSet = new HashSet<int>();
//             
//             foreach (int triIdx in group)
//             {
//                 int baseIdx = triIdx * 3;
//                 strip.triangleIndices.Add(triangles[baseIdx]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 1]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 2]);
//                 
//                 vertSet.Add(triangles[baseIdx]);
//                 vertSet.Add(triangles[baseIdx + 1]);
//                 vertSet.Add(triangles[baseIdx + 2]);
//             }
//             
//             strip.vertexIndices = vertSet.ToList();
//             
//             if (uvs != null && uvs.Length > 0 && strip.vertexIndices.Count > 0)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//                 
//                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//                 
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//             }
//             
//             hairStrips.Add(strip);
//         }
//     }
//
//     /// <summary>
//     /// Scene视图绘制
//     /// </summary>
//     private void OnSceneGUI(SceneView sceneView)
//     {
//         if (!analysisComplete || targetObject == null || hairStrips.Count == 0 || analyzedMesh == null)
//             return;
//         
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         Transform transform = targetObject.transform;
//         
//         Handles.matrix = Matrix4x4.identity;
//         
//         if (showAllStrips)
//         {
//             foreach (var strip in hairStrips)
//             {
//                 float alpha = strip.index == currentStripIndex ? 1f : 0.2f;
//                 DrawStrip(strip, vertices, uvs, transform, alpha);
//             }
//         }
//         else if (currentStripIndex < hairStrips.Count)
//         {
//             DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
//         }
//     }
//
//     private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
//     {
//         Color stripColor = strip.debugColor;
//         
//         // 绘制三角形面
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawAAConvexPolygon(v0, v1, v2);
//         }
//         
//         // 绘制边
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.8f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawLine(v0, v1);
//             Handles.DrawLine(v1, v2);
//             Handles.DrawLine(v2, v0);
//         }
//         
//         // 绘制顶点（使用当前选择的UV差值模式着色）
//         foreach (int vertIdx in strip.vertexIndices)
//         {
//             Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
//             float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;
//             
//             // 使用当前模式计算差值
//             float diff = CalculateUVDifference(vValue, strip);
//             
//             // 根据模式决定颜色映射
//             Color vertColor;
//             if (uvDifferenceMode == UVDifferenceMode.GlobalV)
//             {
//                 // GlobalV模式：根部=0(绿色), 尖端=1(红色)
//                 vertColor = Color.Lerp(Color.green, Color.red, diff);
//             }
//             else
//             {
//                 // 其他模式：根部=1(绿色), 尖端=0(红色)
//                 vertColor = Color.Lerp(Color.red, Color.green, diff);
//             }
//             vertColor.a = alpha;
//             
//             Handles.color = vertColor;
//             Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);
//             
//             // 标签
//             if ((showVertexLabels || showUVInfo) && alpha > 0.5f)
//             {
//                 string label = "";
//                 if (showVertexLabels) label += $"[{vertIdx}]";
//                 if (showUVInfo) label += $" V:{vValue:F3} D:{diff:F2}";
//                 Handles.Label(worldPos + Vector3.up * vertexSphereSize * 1.5f, label, EditorStyles.miniLabel);
//             }
//         }
//         
//         // 绘制根部和尖端标记
//         if (showRootTipMarkers && alpha > 0.5f)
//         {
//             float rootDiff = CalculateUVDifference(strip.maxV, strip);
//             float tipDiff = CalculateUVDifference(strip.minV, strip);
//             
//             // ROOT标记 - 绿色大球
//             Handles.color = Color.green;
//             Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.rootPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"ROOT\nV={strip.maxV:F3}\nDiff={rootDiff:F3}", EditorStyles.whiteBoldLabel);
//             
//             // TIP标记 - 红色大球
//             Handles.color = Color.red;
//             Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.tipPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"TIP\nV={strip.minV:F3}\nDiff={tipDiff:F3}", EditorStyles.whiteBoldLabel);
//             
//             // 连接线
//             Handles.color = Color.yellow;
//             Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 3f);
//         }
//     }
//
//     private void FocusOnStrip(int index)
//     {
//         if (index >= hairStrips.Count) return;
//         
//         var strip = hairStrips[index];
//         Vector3 center = (strip.rootPosition + strip.tipPosition) / 2f;
//         float size = Mathf.Max(Vector3.Distance(strip.rootPosition, strip.tipPosition) * 3f, 0.1f);
//         
//         SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, size);
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 生成带UV差值的Mesh
//     /// </summary>
//     private void GenerateMeshWithUVDifference()
//     {
//         Mesh newMesh = Instantiate(analyzedMesh);
//         newMesh.name = analyzedMesh.name + $"_UVDiff_{uvDifferenceMode}";
//         
//         Vector2[] uvs = newMesh.uv;
//         Color[] colors = new Color[newMesh.vertexCount];
//         
//         // 初始化
//         for (int i = 0; i < colors.Length; i++)
//             colors[i] = new Color(1, 1, 0, 1);
//         
//         // 创建顶点到毛发片的映射
//         Dictionary<int, HairStrip> vertexToStrip = new Dictionary<int, HairStrip>();
//         foreach (var strip in hairStrips)
//         {
//             foreach (int vertIdx in strip.vertexIndices)
//             {
//                 if (!vertexToStrip.ContainsKey(vertIdx))
//                 {
//                     vertexToStrip[vertIdx] = strip;
//                 }
//             }
//         }
//         
//         // 计算每个顶点的差值
//         for (int i = 0; i < colors.Length; i++)
//         {
//             float v = uvs[i].y;
//             float diff = 0f;
//             
//             if (vertexToStrip.ContainsKey(i))
//             {
//                 HairStrip strip = vertexToStrip[i];
//                 diff = CalculateUVDifference(v, strip);
//             }
//             else
//             {
//                 // 对于未分配到毛发片的顶点，使用全局归一化
//                 diff = 0;//globalVRange > 0.001f ? (v - globalMaxV) / globalVRange : 0f;
//             }
//             
//             colors[i].b = diff; // 存储到B通道
//         }
//         
//         newMesh.colors = colors;
//         
//         // 应用并保存
//         ApplyMesh(newMesh);
//         
//         string path = EditorUtility.SaveFilePanelInProject(
//             "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");
//         
//         if (!string.IsNullOrEmpty(path))
//         {
//             AssetDatabase.CreateAsset(newMesh, path);
//             AssetDatabase.SaveAssets();
//             Debug.Log($"✓ Mesh已保存: {path}");
//             Debug.Log($"UV差值模式: {uvDifferenceMode}");
//             Debug.Log("UV差值已存储到顶点颜色B通道 (根部=1, 尖端=0)");
//         }
//     }
//     
//     /// <summary>
//     /// 导出单个毛发片（带错误处理）
//     /// </summary>
//     private void ExportSingleStrip(HairStrip strip)
//     {
//         if (strip == null)
//         {
//             EditorUtility.DisplayDialog("错误", "毛发片数据为空", "确定");
//             return;
//         }
//     
//         if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 顶点数不足 ({strip.vertexIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 三角形数不足 ({strip.triangleIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         try
//         {
//             Mesh mesh = CreateMeshFromStrip(strip);
//         
//             if (mesh == null || mesh.vertexCount == 0)
//             {
//                 EditorUtility.DisplayDialog("错误", "生成Mesh失败", "确定");
//                 return;
//             }
//         
//             string path = EditorUtility.SaveFilePanelInProject(
//                 "保存毛发片", 
//                 $"HairStrip_{strip.index}_{uvDifferenceMode}", 
//                 "asset", 
//                 "选择保存位置");
//         
//             if (!string.IsNullOrEmpty(path))
//             {
//                 if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                 {
//                     AssetDatabase.DeleteAsset(path);
//                 }
//             
//                 AssetDatabase.CreateAsset(mesh, path);
//                 AssetDatabase.SaveAssets();
//             
//                 Debug.Log($"✓ 毛发片 #{strip.index} 已导出到: {path}");
//                 Debug.Log($"  UV差值模式: {uvDifferenceMode}");
//                 Debug.Log($"  顶点数: {mesh.vertexCount}, 三角形数: {mesh.triangles.Length / 3}");
//             }
//         }
//         catch (System.Exception e)
//         {
//             EditorUtility.DisplayDialog("导出失败", $"错误: {e.Message}", "确定");
//             Debug.LogError($"导出毛发片 #{strip.index} 失败: {e}");
//         }
//     }
//
//     /// <summary>
//     /// 导出所有毛发片（带错误处理）
//     /// </summary>
//     private void ExportAllStrips()
//     {
//         string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
//         if (string.IsNullOrEmpty(folder)) return;
//
//         if (folder.StartsWith(Application.dataPath))
//         {
//             folder = "Assets" + folder.Substring(Application.dataPath.Length);
//         }
//
//         if (!AssetDatabase.IsValidFolder(folder))
//         {
//             Debug.LogError($"无效的文件夹路径: {folder}");
//             return;
//         }
//
//         int successCount = 0;
//         int failCount = 0;
//         List<string> failedStrips = new List<string>();
//
//         try
//         {
//             for (int i = 0; i < hairStrips.Count; i++)
//             {
//                 var strip = hairStrips[i];
//
//                 bool cancel = EditorUtility.DisplayCancelableProgressBar(
//                     "导出毛发片",
//                     $"正在导出 {i + 1}/{hairStrips.Count}: HairStrip_{strip.index}",
//                     (float)i / hairStrips.Count);
//
//                 if (cancel)
//                 {
//                     Debug.Log("用户取消导出");
//                     break;
//                 }
//
//                 try
//                 {
//                     if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//                     {
//                         failedStrips.Add($"#{strip.index}: 顶点数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//                     {
//                         failedStrips.Add($"#{strip.index}: 三角形数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     Mesh mesh = CreateMeshFromStrip(strip);
//
//                     if (mesh != null && mesh.vertexCount > 0)
//                     {
//                         string path = $"{folder}/HairStrip_{strip.index}.asset";
//
//                         if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                         {
//                             AssetDatabase.DeleteAsset(path);
//                         }
//
//                         AssetDatabase.CreateAsset(mesh, path);
//                         successCount++;
//                     }
//                     else
//                     {
//                         failedStrips.Add($"#{strip.index}: 生成Mesh失败");
//                         failCount++;
//                     }
//                 }
//                 catch (System.Exception e)
//                 {
//                     failedStrips.Add($"#{strip.index}: {e.Message}");
//                     failCount++;
//                     Debug.LogError($"导出毛发片 #{strip.index} 失败: {e.Message}");
//                 }
//             }
//         }
//         finally
//         {
//             EditorUtility.ClearProgressBar();
//         }
//
//         AssetDatabase.SaveAssets();
//         AssetDatabase.Refresh();
//
//         string message = $"导出完成！\n成功: {successCount}\n失败: {failCount}\nUV差值模式: {uvDifferenceMode}";
//
//         if (failedStrips.Count > 0)
//         {
//             message += $"\n\n失败详情:\n{string.Join("\n", failedStrips.Take(10))}";
//             if (failedStrips.Count > 10)
//             {
//                 message += $"\n... 还有 {failedStrips.Count - 10} 个";
//             }
//         }
//
//         EditorUtility.DisplayDialog("导出结果", message, "确定");
//
//         Debug.Log($"✓ 毛发片导出完成: 成功 {successCount}, 失败 {failCount}, 保存到 {folder}");
//     }
//
//     private void ExportAnalysisReport()
//     {
//         string path = EditorUtility.SaveFilePanel("保存分析报告", "", "HairAnalysisReport", "txt");
//         if (string.IsNullOrEmpty(path)) return;
//         
//         var sb = new System.Text.StringBuilder();
//         sb.AppendLine("========== 毛发分析报告 ==========");
//         sb.AppendLine($"物体: {targetObject.name}");
//         sb.AppendLine($"Mesh: {analyzedMesh.name}");
//         sb.AppendLine($"总顶点数: {analyzedMesh.vertexCount}");
//         sb.AppendLine($"总三角形数: {analyzedMesh.triangles.Length / 3}");
//         sb.AppendLine($"识别毛发片数: {hairStrips.Count}");
//         sb.AppendLine();
//         sb.AppendLine("---------- 全局UV统计 ----------");
//         sb.AppendLine($"全局 Min V: {globalMinV:F4}");
//         sb.AppendLine($"全局 Max V: {globalMaxV:F4}");
//         sb.AppendLine($"全局 V Range: {globalVRange:F4}");
//         sb.AppendLine();
//         sb.AppendLine($"当前UV差值模式: {uvDifferenceMode}");
//         sb.AppendLine();
//         sb.AppendLine("UV规则: ROOT(根部)=V值最大, TIP(尖端)=V值最小");
//         sb.AppendLine();
//         sb.AppendLine("---------- UV差值计算公式 ----------");
//         switch (uvDifferenceMode)
//         {
//             case UVDifferenceMode.PerStrip:
//                 sb.AppendLine("PerStrip: diff =(V - 片内minV)/ 片内vRange");
//                 break;
//             case UVDifferenceMode.GlobalV:
//                 sb.AppendLine("GlobalV: diff = (全局maxV - V)  / (全局maxV - 片内minV)");
//                 break;
//             case UVDifferenceMode.GlobalRange:
//                 sb.AppendLine("GlobalRange: diff = (全局maxV - v) / 全局vRange");
//                 break;
//         }
//         sb.AppendLine();
//         sb.AppendLine("---------- 各毛发片详情 ----------");
//         
//         foreach (var strip in hairStrips)
//         {
//             float rootDiff = CalculateUVDifference(strip.maxV, strip);
//             float tipDiff = CalculateUVDifference(strip.minV, strip);
//             
//             sb.AppendLine($"\n毛发片 #{strip.index}:");
//             sb.AppendLine($"  顶点数: {strip.vertexCount}");
//             sb.AppendLine($"  三角形数: {strip.triangleCount}");
//             sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4}");
//             sb.AppendLine($"  V值跨度: {strip.vRange:F4}");
//             sb.AppendLine($"  根部差值: {rootDiff:F4}");
//             sb.AppendLine($"  尖端差值: {tipDiff:F4}");
//             sb.AppendLine($"  顶点索引: {string.Join(",", strip.vertexIndices.Take(30))}{(strip.vertexIndices.Count > 30 ? "..." : "")}");
//         }
//         
//         System.IO.File.WriteAllText(path, sb.ToString());
//         Debug.Log($"✓ 报告已保存: {path}");
//     }
//
//     /// <summary>
//     /// 从毛发片创建独立Mesh（使用当前UV差值模式）
//     /// </summary>
//     private Mesh CreateMeshFromStrip(HairStrip strip)
//     {
//         Vector3[] origVerts = analyzedMesh.vertices;
//         Vector2[] origUVs = analyzedMesh.uv;
//         Vector3[] origNormals = analyzedMesh.normals;
//         Color[] origColors = analyzedMesh.colors;
//
//         HashSet<int> allVertices = new HashSet<int>(strip.vertexIndices);
//
//         for (int i = 0; i < strip.triangleIndices.Count; i++)
//         {
//             int vertIdx = strip.triangleIndices[i];
//             if (!allVertices.Contains(vertIdx))
//             {
//                 allVertices.Add(vertIdx);
//                 Debug.LogWarning($"毛发片 #{strip.index}: 三角形引用了未在顶点列表中的顶点 {vertIdx}，已自动添加");
//             }
//         }
//
//         List<int> finalVertexList = allVertices.ToList();
//
//         Dictionary<int, int> remap = new Dictionary<int, int>();
//         for (int i = 0; i < finalVertexList.Count; i++)
//         {
//             remap[finalVertexList[i]] = i;
//         }
//
//         int vertCount = finalVertexList.Count;
//         Vector3[] newVerts = new Vector3[vertCount];
//         Vector2[] newUVs = new Vector2[vertCount];
//         Vector3[] newNormals = new Vector3[vertCount];
//         Color[] newColors = new Color[vertCount];
//
//         for (int i = 0; i < vertCount; i++)
//         {
//             int origIdx = finalVertexList[i];
//
//             newVerts[i] = origVerts[origIdx];
//
//             newUVs[i] = (origUVs != null && origIdx < origUVs.Length)
//                 ? origUVs[origIdx]
//                 : Vector2.zero;
//
//             newNormals[i] = (origNormals != null && origIdx < origNormals.Length)
//                 ? origNormals[origIdx]
//                 : Vector3.up;
//
//             newColors[i] = (origColors != null && origIdx < origColors.Length)
//                 ? origColors[origIdx]
//                 : Color.white;
//         }
//
//         List<int> newTriangles = new List<int>();
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             if (i + 2 < strip.triangleIndices.Count)
//             {
//                 int idx0 = strip.triangleIndices[i];
//                 int idx1 = strip.triangleIndices[i + 1];
//                 int idx2 = strip.triangleIndices[i + 2];
//
//                 if (remap.ContainsKey(idx0) && remap.ContainsKey(idx1) && remap.ContainsKey(idx2))
//                 {
//                     newTriangles.Add(remap[idx0]);
//                     newTriangles.Add(remap[idx1]);
//                     newTriangles.Add(remap[idx2]);
//                 }
//                 else
//                 {
//                     Debug.LogWarning($"毛发片 #{strip.index}: 跳过无效三角形 ({idx0}, {idx1}, {idx2})");
//                 }
//             }
//         }
//
//         // 使用当前选择的UV差值模式计算差值
//         for (int i = 0; i < vertCount; i++)
//         {
//             float v = newUVs[i].y;
//             float diff = CalculateUVDifference(v, strip);
//             newColors[i].b = diff;
//         }
//
//         Mesh mesh = new Mesh();
//         mesh.name = $"HairStrip_{strip.index}";
//         mesh.vertices = newVerts;
//         mesh.uv = newUVs;
//         mesh.normals = newNormals;
//         mesh.colors = newColors;
//
//         if (newTriangles.Count >= 3)
//         {
//             mesh.triangles = newTriangles.ToArray();
//         }
//         else
//         {
//             Debug.LogWarning($"毛发片 #{strip.index}: 三角形数量不足 ({newTriangles.Count / 3})");
//         }
//
//         mesh.RecalculateBounds();
//
//         return mesh;
//     }
//
//     #region Helper Methods
//     
//     private Mesh GetMesh()
//     {
//         if (targetObject == null) return null;
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         return mf?.sharedMesh ?? smr?.sharedMesh;
//     }
//     
//     private void ApplyMesh(Mesh mesh)
//     {
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         if (mf != null) mf.sharedMesh = mesh;
//         else if (smr != null) smr.sharedMesh = mesh;
//     }
//     
//     private Dictionary<int, HashSet<int>> BuildAdjacencyList(int[] triangles, int vertexCount)
//     {
//         var adj = new Dictionary<int, HashSet<int>>();
//         for (int i = 0; i < vertexCount; i++) adj[i] = new HashSet<int>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
//             adj[v0].Add(v1); adj[v0].Add(v2);
//             adj[v1].Add(v0); adj[v1].Add(v2);
//             adj[v2].Add(v0); adj[v2].Add(v1);
//         }
//         return adj;
//     }
//     
//     private Dictionary<int, List<int>> BuildVertexToTrianglesMap(int[] triangles)
//     {
//         var map = new Dictionary<int, List<int>>();
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIdx = i / 3;
//             for (int j = 0; j < 3; j++)
//             {
//                 int v = triangles[i + j];
//                 if (!map.ContainsKey(v)) map[v] = new List<int>();
//                 map[v].Add(triIdx);
//             }
//         }
//         return map;
//     }
//     
//     private void AddEdgeTriangle(Dictionary<Edge, List<int>> dict, int v0, int v1, int triIndex)
//     {
//         Edge edge = new Edge(v0, v1);
//         if (!dict.ContainsKey(edge)) dict[edge] = new List<int>();
//         dict[edge].Add(triIndex);
//     }
//     
//     public struct Edge : System.IEquatable<Edge>
//     {
//         public int v0, v1;
//         public Edge(int a, int b) { v0 = Mathf.Min(a, b); v1 = Mathf.Max(a, b); }
//         public bool Equals(Edge other) => v0 == other.v0 && v1 == other.v1;
//         public override int GetHashCode() => v0 ^ (v1 << 16);
//     }
//     
//     public class UnionFind
//     {
//         private int[] parent, rank;
//         public UnionFind(int n)
//         {
//             parent = new int[n]; rank = new int[n];
//             for (int i = 0; i < n; i++) parent[i] = i;
//         }
//         public int Find(int x) { if (parent[x] != x) parent[x] = Find(parent[x]); return parent[x]; }
//         public void Union(int x, int y)
//         {
//             int px = Find(x), py = Find(y);
//             if (px == py) return;
//             if (rank[px] < rank[py]) parent[px] = py;
//             else if (rank[px] > rank[py]) parent[py] = px;
//             else { parent[py] = px; rank[px]++; }
//         }
//     }
//     
//     #endregion
// }
//------------------------------------以下修改是添加被排除的顶点的日志，本人发现有些头发没有被纳入片------------------------
// using UnityEngine;
// using UnityEditor;
// using System.Collections.Generic;
// using System.Linq;
//
// public class HairAnalyzerVisualizer : EditorWindow
// {
//     private GameObject targetObject;
//     private Mesh analyzedMesh;
//     
//     // 分析结果
//     private List<HairStrip> hairStrips = new List<HairStrip>();
//     private int currentStripIndex = 0;
//     
//     // 全局UV统计
//     private float globalMinV = 0f;
//     private float globalMaxV = 1f;
//     private float globalVRange = 1f;
//     
//     // 可视化设置
//     private bool showAllStrips = true;
//     private bool showVertexLabels = false;
//     private bool showUVInfo = true;
//     private bool showRootTipMarkers = true;
//     private float vertexSphereSize = 0.002f;
//     
//     // 分析参数
//     private float rootThreshold = 0.05f;
//     private float uvContinuityThreshold = 0.3f;
//     private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
//     
//     // 【新增】UV差值计算模式
//     private UVDifferenceMode uvDifferenceMode = UVDifferenceMode.PerStrip;
//     
//     // 【新增】日志设置
//     private bool enableDetailedLog = false;
//     private bool logToFile = false;
//     private int maxLogEntries = 100; // 控制台最大输出条数
//     
//     // 【新增】排除统计
//     private Dictionary<string, int> exclusionStats = new Dictionary<string, int>();
//     private List<string> detailedLogs = new List<string>();
//     
//     private Vector2 scrollPos;
//     private bool analysisComplete = false;
//     
//     public enum AnalysisMethod
//     {
//         UVBased,
//         TriangleStrip,
//         ConnectedComponent
//     }
//     
//     /// <summary>
//     /// UV差值计算模式
//     /// </summary>
//     public enum UVDifferenceMode
//     {
//         [InspectorName("单片独立计算")]
//         PerStrip,           // 每个毛发片独立计算（原有模式）
//         [InspectorName("全局V值计算")]
//         GlobalV,            // 使用全局最大V值计算
//         [InspectorName("全局范围归一化")]
//         GlobalRange         // 使用全局V范围归一化
//     }
//
//     /// <summary>
//     /// 毛发条带数据
//     /// </summary>
//     public class HairStrip
//     {
//         public int index;
//         public List<int> vertexIndices = new List<int>();
//         public List<int> triangleIndices = new List<int>();
//         public Color debugColor;
//         
//         // UV统计 - 注意：maxV是根部，minV是尖端
//         public float minV; // 尖端（TIP）
//         public float maxV; // 根部（ROOT）
//         
//         public Vector3 rootPosition; // V值最大的点
//         public Vector3 tipPosition;  // V值最小的点
//         
//         public int vertexCount => vertexIndices.Count;
//         public int triangleCount => triangleIndices.Count / 3;
//         public float vRange => maxV - minV;
//     }
//
//     [MenuItem("Tools/Hair/Hair Analyzer Visualizer")]
//     public static void ShowWindow()
//     {
//         var window = GetWindow<HairAnalyzerVisualizer>("毛发分析可视化");
//         window.minSize = new Vector2(420, 800);
//     }
//
//     private void OnEnable()
//     {
//         SceneView.duringSceneGui += OnSceneGUI;
//     }
//
//     private void OnDisable()
//     {
//         SceneView.duringSceneGui -= OnSceneGUI;
//     }
//
//     private void OnGUI()
//     {
//         scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
//         
//         DrawHeader();
//         DrawInputSection();
//         DrawAnalysisSettings();
//         DrawLogSettings(); // 新增日志设置
//         DrawAnalysisButtons();
//         
//         if (analysisComplete)
//         {
//             DrawResultsSection();
//             DrawExclusionStats(); // 新增排除统计显示
//             DrawStripNavigator();
//             DrawVisualizationSettings();
//             DrawExportSection();
//         }
//         
//         EditorGUILayout.EndScrollView();
//     }
//
//     private void DrawHeader()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
//         {
//             fontSize = 16,
//             alignment = TextAnchor.MiddleCenter
//         };
//         GUILayout.Label("🔍 毛发结构分析与可视化", titleStyle);
//         
//         EditorGUILayout.Space(5);
//         
//         EditorGUILayout.HelpBox(
//             "UV规则：\n" +
//             "• ROOT（根部）= V值最大 → 显示为绿色\n" +
//             "• TIP（尖端）= V值最小 → 显示为红色\n" +
//             "• 差值结果：根部=1，尖端=0", 
//             MessageType.Info);
//         
//         EditorGUILayout.Space(10);
//     }
//
//     private void DrawInputSection()
//     {
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📥 输入", EditorStyles.boldLabel);
//         
//         EditorGUI.BeginChangeCheck();
//         targetObject = (GameObject)EditorGUILayout.ObjectField(
//             "目标物体", targetObject, typeof(GameObject), true);
//         if (EditorGUI.EndChangeCheck())
//         {
//             analysisComplete = false;
//             hairStrips.Clear();
//         }
//         
//         if (targetObject != null)
//         {
//             Mesh mesh = GetMesh();
//             if (mesh != null)
//             {
//                 EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
//                 EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
//                 
//                 if (mesh.uv != null && mesh.uv.Length > 0)
//                 {
//                     float minV = mesh.uv.Min(uv => uv.y);
//                     float maxV = mesh.uv.Max(uv => uv.y);
//                     EditorGUILayout.LabelField("UV V值范围", $"{minV:F3} ~ {maxV:F3}");
//                 }
//                 else
//                 {
//                     EditorGUILayout.HelpBox("警告：Mesh没有UV数据！", MessageType.Warning);
//                 }
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("⚙️ 分析设置", EditorStyles.boldLabel);
//         
//         analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
//         
//         string methodDesc = "";
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 methodDesc = "从V值最大的点(根部)出发，沿V递减方向追踪";
//                 break;
//             case AnalysisMethod.TriangleStrip:
//                 methodDesc = "通过共享边的三角形分组";
//                 break;
//             case AnalysisMethod.ConnectedComponent:
//                 methodDesc = "完全独立的三角形组为一片";
//                 break;
//         }
//         EditorGUILayout.HelpBox(methodDesc, MessageType.None);
//         
//         rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
//         uvContinuityThreshold = EditorGUILayout.Slider("UV连续性阈值", uvContinuityThreshold, 0.1f, 0.5f);
//         
//         EditorGUILayout.Space(5);
//         EditorGUILayout.LabelField("UV差值计算", EditorStyles.boldLabel);
//         
//         uvDifferenceMode = (UVDifferenceMode)EditorGUILayout.EnumPopup("计算模式", uvDifferenceMode);
//         
//         // 显示模式说明
//         string modeDesc = "";
//         switch (uvDifferenceMode)
//         {
//             case UVDifferenceMode.PerStrip:
//                 modeDesc = "每片毛发独立归一化\ndiff = (V - 片内minV) / 片内vRange\n根部=1, 尖端=0";
//                 break;
//             case UVDifferenceMode.GlobalV:
//                 modeDesc = "统一根部起点（全局maxV）\ndiff = (全局maxV - 片内maxV) \n根部=1, 尖端=0";
//                 break;
//             case UVDifferenceMode.GlobalRange:
//                 modeDesc = "使用全局V范围归一化\ndiff = (V - 全局minV) / 全局vRange\n根部=1, 尖端=0";
//                 break;
//         }
//         EditorGUILayout.HelpBox(modeDesc, MessageType.None);
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 【新增】日志设置UI
//     /// </summary>
//     private void DrawLogSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📋 日志设置", EditorStyles.boldLabel);
//         
//         enableDetailedLog = EditorGUILayout.Toggle("启用详细日志", enableDetailedLog);
//         
//         if (enableDetailedLog)
//         {
//             EditorGUI.indentLevel++;
//             maxLogEntries = EditorGUILayout.IntSlider("控制台最大条数", maxLogEntries, 10, 500);
//             logToFile = EditorGUILayout.Toggle("同时输出到文件", logToFile);
//             EditorGUI.indentLevel--;
//             
//             EditorGUILayout.HelpBox(
//                 "详细日志会记录：\n" +
//                 "• 根部顶点识别过程\n" +
//                 "• 每个顶点的邻居判断\n" +
//                 "• 排除原因统计", 
//                 MessageType.Info);
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 【新增】排除统计显示
//     /// </summary>
//     private void DrawExclusionStats()
//     {
//         if (exclusionStats.Count == 0) return;
//         
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📊 顶点排除统计", EditorStyles.boldLabel);
//         
//         foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
//         {
//             EditorGUILayout.BeginHorizontal();
//             EditorGUILayout.LabelField(kvp.Key, GUILayout.Width(250));
//             EditorGUILayout.LabelField(kvp.Value.ToString(), EditorStyles.boldLabel);
//             EditorGUILayout.EndHorizontal();
//         }
//         
//         EditorGUILayout.Space(3);
//         if (GUILayout.Button("导出详细日志"))
//         {
//             ExportDetailedLog();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawAnalysisButtons()
//     {
//         EditorGUILayout.Space(10);
//         
//         GUI.enabled = targetObject != null && GetMesh() != null;
//         
//         GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
//         if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
//         {
//             PerformAnalysis();
//         }
//         GUI.backgroundColor = Color.white;
//         
//         GUI.enabled = true;
//     }
//
//     private void DrawResultsSection()
//     {
//         EditorGUILayout.Space(10);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
//         
//         EditorGUILayout.LabelField("识别到的毛发片", hairStrips.Count.ToString());
//         
//         // 显示全局UV统计
//         EditorGUILayout.Space(3);
//         EditorGUILayout.LabelField("全局UV统计", EditorStyles.boldLabel);
//         EditorGUILayout.BeginHorizontal();
//         EditorGUILayout.LabelField($"全局 Min V: {globalMinV:F4}", GUILayout.Width(150));
//         EditorGUILayout.LabelField($"全局 Max V: {globalMaxV:F4}");
//         EditorGUILayout.EndHorizontal();
//         EditorGUILayout.LabelField($"全局 V Range: {globalVRange:F4}");
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.Space(3);
//             var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
//             var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
//             var vRanges = hairStrips.Select(s => s.vRange).ToList();
//             
//             EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} ~ {vertexCounts.Max()} (平均:{vertexCounts.Average():F1})");
//             EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} ~ {triCounts.Max()}");
//             EditorGUILayout.LabelField("单片V值跨度范围", $"{vRanges.Min():F3} ~ {vRanges.Max():F3}");
//             
//             // 检测异常
//             int tooSmall = hairStrips.Count(s => s.vertexCount < 3);
//             int tooLarge = hairStrips.Count(s => s.vertexCount > 50);
//             int noVRange = hairStrips.Count(s => s.vRange < 0.01f);
//             
//             if (tooSmall > 0 || tooLarge > 0 || noVRange > 0)
//             {
//                 string warning = "检测到异常：\n";
//                 if (tooSmall > 0) warning += $"• {tooSmall} 片顶点数过少(<3)\n";
//                 if (tooLarge > 0) warning += $"• {tooLarge} 片顶点数过多(>50)\n";
//                 if (noVRange > 0) warning += $"• {noVRange} 片V值跨度过小(<0.01)";
//                 EditorGUILayout.HelpBox(warning, MessageType.Warning);
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawStripNavigator()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
//         
//         if (hairStrips.Count > 0)
//         {
//             EditorGUILayout.BeginHorizontal();
//             
//             if (GUILayout.Button("◀", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
//             
//             if (GUILayout.Button("▶", GUILayout.Width(40)))
//             {
//                 currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
//                 FocusOnStrip(currentStripIndex);
//             }
//             
//             EditorGUILayout.EndHorizontal();
//             
//             // 当前毛发片详情
//             if (currentStripIndex < hairStrips.Count)
//             {
//                 var strip = hairStrips[currentStripIndex];
//                 
//                 EditorGUILayout.Space(5);
//                 EditorGUILayout.BeginVertical("helpbox");
//                 
//                 EditorGUILayout.LabelField($"毛发片 #{strip.index}", EditorStyles.boldLabel);
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString(), GUILayout.Width(150));
//                 EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 EditorGUILayout.LabelField("根部V值(MAX)", $"{strip.maxV:F4}", GUILayout.Width(150));
//                 EditorGUILayout.LabelField("尖端V值(MIN)", $"{strip.minV:F4}");
//                 EditorGUILayout.EndHorizontal();
//                 
//                 EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F4}");
//                 
//                 // 显示当前模式下的差值计算预览
//                 float rootDiff = CalculateUVDifference(strip.maxV, strip);
//                 float tipDiff = CalculateUVDifference(strip.minV, strip);
//                 EditorGUILayout.LabelField($"差值预览 ({uvDifferenceMode})", $"根部={rootDiff:F3}, 尖端={tipDiff:F3}");
//                 
//                 // 顶点列表预览
//                 string vertPreview = string.Join(", ", strip.vertexIndices.Take(15));
//                 if (strip.vertexIndices.Count > 15) vertPreview += "...";
//                 EditorGUILayout.LabelField("顶点:", vertPreview, EditorStyles.miniLabel);
//                 
//                 EditorGUILayout.EndVertical();
//                 
//                 EditorGUILayout.BeginHorizontal();
//                 if (GUILayout.Button("聚焦此片"))
//                 {
//                     FocusOnStrip(currentStripIndex);
//                 }
//                 if (GUILayout.Button("导出此片"))
//                 {
//                     ExportSingleStrip(strip);
//                 }
//                 EditorGUILayout.EndHorizontal();
//             }
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawVisualizationSettings()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
//         
//         showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
//         showVertexLabels = EditorGUILayout.Toggle("显示顶点索引", showVertexLabels);
//         showUVInfo = EditorGUILayout.Toggle("显示UV V值", showUVInfo);
//         showRootTipMarkers = EditorGUILayout.Toggle("显示根部/尖端标记", showRootTipMarkers);
//         vertexSphereSize = EditorGUILayout.Slider("顶点大小", vertexSphereSize, 0.0005f, 0.02f);
//         
//         EditorGUILayout.BeginHorizontal();
//         if (GUILayout.Button("刷新视图"))
//         {
//             SceneView.RepaintAll();
//         }
//         if (GUILayout.Button("重置相机"))
//         {
//             if (targetObject != null)
//             {
//                 SceneView.lastActiveSceneView?.LookAt(targetObject.transform.position);
//             }
//         }
//         EditorGUILayout.EndHorizontal();
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     private void DrawExportSection()
//     {
//         EditorGUILayout.Space(5);
//         EditorGUILayout.BeginVertical("box");
//         GUILayout.Label("📤 导出", EditorStyles.boldLabel);
//         
//         // 显示当前使用的UV差值模式
//         EditorGUILayout.LabelField($"当前UV差值模式: {uvDifferenceMode}", EditorStyles.miniLabel);
//         
//         if (GUILayout.Button("生成带UV差值的Mesh"))
//         {
//             GenerateMeshWithUVDifference();
//         }
//         
//         if (GUILayout.Button("导出所有毛发片"))
//         {
//             ExportAllStrips();
//         }
//         
//         if (GUILayout.Button("导出分析报告"))
//         {
//             ExportAnalysisReport();
//         }
//         
//         EditorGUILayout.EndVertical();
//     }
//
//     /// <summary>
//     /// 根据当前模式计算UV差值
//     /// </summary>
//     private float CalculateUVDifference(float vValue, HairStrip strip)
//     {
//         switch (uvDifferenceMode)
//         {
//             case UVDifferenceMode.PerStrip:
//                 // 每片独立计算：(V - 片内minV) / 片内vRange
//                 // 根部(maxV)=1, 尖端(minV)=0
//                 return strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0f;
//                 
//             case UVDifferenceMode.GlobalV:
//                 // 全局V计算：统一根部起点
//                 // diff = (全局maxV - V) / (全局maxV - 片内minV)
//                 // 根部(全局maxV)=0, 尖端(片内minV)=1
//                 // float rangeFromGlobalMax = globalMaxV - strip.minV;
//                 // return rangeFromGlobalMax > 0.001f ? (globalMaxV - vValue) / rangeFromGlobalMax : 0f;
//                 return globalMaxV - strip.maxV;
//                 
//             case UVDifferenceMode.GlobalRange:
//                 // 全局范围归一化：(V - 全局minV) / 全局vRange
//                 // 根部(全局maxV)=1, 尖端(全局minV)=0
//                 return globalVRange > 0.001f ? (vValue - globalMinV) / globalVRange : 0f;
//                 
//             default:
//                 return 0f;
//         }
//     }
//
//     /// <summary>
//     /// 【新增】添加日志条目
//     /// </summary>
//     private void AddLog(string message)
//     {
//         if (!enableDetailedLog) return;
//         detailedLogs.Add($"[{System.DateTime.Now:HH:mm:ss.fff}] {message}");
//     }
//
//     /// <summary>
//     /// 【新增】增加排除统计
//     /// </summary>
//     private void AddExclusionStat(string reason)
//     {
//         if (!exclusionStats.ContainsKey(reason))
//             exclusionStats[reason] = 0;
//         exclusionStats[reason]++;
//     }
//
//     /// <summary>
//     /// 执行分析
//     /// </summary>
//     private void PerformAnalysis()
//     {
//         analyzedMesh = GetMesh();
//         if (analyzedMesh == null) return;
//         
//         hairStrips.Clear();
//         exclusionStats.Clear();
//         detailedLogs.Clear();
//         
//         AddLog("========== 开始毛发分析 ==========");
//         AddLog($"Mesh: {analyzedMesh.name}, 顶点数: {analyzedMesh.vertexCount}, 三角形数: {analyzedMesh.triangles.Length / 3}");
//         
//         // 先计算全局UV统计
//         CalculateGlobalUVStats();
//         AddLog($"全局UV统计: MinV={globalMinV:F4}, MaxV={globalMaxV:F4}, Range={globalVRange:F4}");
//         
//         switch (analysisMethod)
//         {
//             case AnalysisMethod.UVBased:
//                 AnalyzeByUV();
//                 break;
//             case AnalysisMethod.TriangleStrip:
//             case AnalysisMethod.ConnectedComponent:
//                 AnalyzeByConnectedComponent();
//                 break;
//         }
//         
//         // 分配随机颜色
//         System.Random rand = new System.Random(42);
//         foreach (var strip in hairStrips)
//         {
//             strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
//         }
//         
//         analysisComplete = true;
//         currentStripIndex = 0;
//         
//         // 输出日志摘要到控制台
//         Debug.Log($"✓ 分析完成！识别到 {hairStrips.Count} 个毛发片");
//         Debug.Log($"  全局UV范围: V = {globalMinV:F4} ~ {globalMaxV:F4}, Range = {globalVRange:F4}");
//         
//         if (enableDetailedLog)
//         {
//             Debug.Log("---------- 排除统计 ----------");
//             foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
//             {
//                 Debug.Log($"  {kvp.Key}: {kvp.Value}");
//             }
//             
//             // 输出部分详细日志
//             int logCount = Mathf.Min(detailedLogs.Count, maxLogEntries);
//             Debug.Log($"---------- 详细日志 (显示前{logCount}条，共{detailedLogs.Count}条) ----------");
//             for (int i = 0; i < logCount; i++)
//             {
//                 Debug.Log(detailedLogs[i]);
//             }
//             
//             if (logToFile)
//             {
//                 ExportDetailedLog();
//             }
//         }
//         
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 【新增】导出详细日志
//     /// </summary>
//     private void ExportDetailedLog()
//     {
//         string path = EditorUtility.SaveFilePanel("保存详细日志", "", 
//             $"HairAnalysis_Log_{System.DateTime.Now:yyyyMMdd_HHmmss}", "txt");
//         
//         if (string.IsNullOrEmpty(path)) return;
//         
//         var sb = new System.Text.StringBuilder();
//         sb.AppendLine("========== 毛发分析详细日志 ==========");
//         sb.AppendLine($"时间: {System.DateTime.Now}");
//         sb.AppendLine($"物体: {targetObject?.name}");
//         sb.AppendLine($"Mesh: {analyzedMesh?.name}");
//         sb.AppendLine();
//         
//         sb.AppendLine("---------- 参数设置 ----------");
//         sb.AppendLine($"分析方法: {analysisMethod}");
//         sb.AppendLine($"根部阈值: {rootThreshold}");
//         sb.AppendLine($"UV连续性阈值: {uvContinuityThreshold}");
//         sb.AppendLine($"UV差值模式: {uvDifferenceMode}");
//         sb.AppendLine();
//         
//         sb.AppendLine("---------- 排除统计 ----------");
//         foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
//         {
//             sb.AppendLine($"{kvp.Key}: {kvp.Value}");
//         }
//         sb.AppendLine();
//         
//         sb.AppendLine("---------- 详细日志 ----------");
//         foreach (var log in detailedLogs)
//         {
//             sb.AppendLine(log);
//         }
//         
//         System.IO.File.WriteAllText(path, sb.ToString());
//         Debug.Log($"✓ 详细日志已保存到: {path}");
//     }
//
//     /// <summary>
//     /// 计算全局UV统计
//     /// </summary>
//     private void CalculateGlobalUVStats()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         if (uvs == null || uvs.Length == 0)
//         {
//             globalMinV = 0f;
//             globalMaxV = 1f;
//             globalVRange = 1f;
//             return;
//         }
//         
//         globalMinV = float.MaxValue;
//         globalMaxV = float.MinValue;
//         
//         foreach (var uv in uvs)
//         {
//             if (uv.y < globalMinV) globalMinV = uv.y;
//             if (uv.y > globalMaxV) globalMaxV = uv.y;
//         }
//         
//         globalVRange = globalMaxV - globalMinV;
//         
//         // 防止除零
//         if (globalVRange < 0.001f)
//         {
//             globalVRange = 1f;
//         }
//     }
//
//     // /// <summary>
//     // /// 基于UV分析（带详细日志）
//     // /// </summary>
//     // private void AnalyzeByUV()
//     // {
//     //     Vector2[] uvs = analyzedMesh.uv;
//     //     Vector3[] vertices = analyzedMesh.vertices;
//     //     int[] triangles = analyzedMesh.triangles;
//     //
//     //     if (uvs == null || uvs.Length == 0)
//     //     {
//     //         EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//     //         return;
//     //     }
//     //
//     //     AddLog("开始构建邻接表...");
//     //     var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//     //     var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//     //     AddLog($"邻接表构建完成，共 {adjacency.Count} 个顶点");
//     //
//     //     // ========== 第一步：识别根部顶点 ==========
//     //     AddLog("");
//     //     AddLog("========== 第一步：识别根部顶点 ==========");
//     //     AddLog($"判断条件：V值 >= {globalMaxV:F4} - {rootThreshold} = {globalMaxV - rootThreshold:F4}");
//     //     AddLog($"或者：是局部最大值且有更低的邻居");
//     //     
//     //     List<int> rootVertices = new List<int>();
//     //     int globalMaxRoots = 0;
//     //     int localMaxRoots = 0;
//     //     int rejectedAsRoot = 0;
//     //
//     //     for (int i = 0; i < uvs.Length; i++)
//     //     {
//     //         float v = uvs[i].y;
//     //         
//     //         // 条件1：V值接近全局最大
//     //         if (v >= globalMaxV - rootThreshold)
//     //         {
//     //             rootVertices.Add(i);
//     //             globalMaxRoots++;
//     //             AddLog($"  顶点[{i}] V={v:F4} → ✓ 根部(接近全局最大 {globalMaxV:F4})");
//     //             continue;
//     //         }
//     //
//     //         // 条件2：局部最大值
//     //         if (adjacency.ContainsKey(i) && adjacency[i].Count > 0)
//     //         {
//     //             bool isLocalMax = adjacency[i].All(n => uvs[n].y <= v + 0.001f);
//     //             bool hasLowerNeighbor = adjacency[i].Any(n => uvs[n].y < v - 0.02f);
//     //
//     //             if (isLocalMax && hasLowerNeighbor)
//     //             {
//     //                 rootVertices.Add(i);
//     //                 localMaxRoots++;
//     //                 
//     //                 float maxNeighborV = adjacency[i].Max(n => uvs[n].y);
//     //                 float minNeighborV = adjacency[i].Min(n => uvs[n].y);
//     //                 AddLog($"  顶点[{i}] V={v:F4} → ✓ 根部(局部最大, 邻居V范围:{minNeighborV:F4}~{maxNeighborV:F4})");
//     //             }
//     //             else if (enableDetailedLog && v > globalMaxV - 0.2f) // 只记录高V值但未被选中的
//     //             {
//     //                 rejectedAsRoot++;
//     //                 string reason = "";
//     //                 if (!isLocalMax) reason += "不是局部最大 ";
//     //                 if (!hasLowerNeighbor) reason += "没有明显更低的邻居";
//     //                 AddLog($"  顶点[{i}] V={v:F4} → ✗ 非根部({reason.Trim()})");
//     //             }
//     //         }
//     //     }
//     //
//     //     AddLog($"");
//     //     AddLog($"根部顶点识别结果：共 {rootVertices.Count} 个");
//     //     AddLog($"  - 接近全局最大：{globalMaxRoots} 个");
//     //     AddLog($"  - 局部最大值：{localMaxRoots} 个");
//     //     AddLog($"  - 被排除（高V值）：{rejectedAsRoot} 个");
//     //     
//     //     AddExclusionStat($"根部识别-接近全局最大V");
//     //     exclusionStats[$"根部识别-接近全局最大V"] = globalMaxRoots;
//     //     AddExclusionStat($"根部识别-局部最大值");
//     //     exclusionStats[$"根部识别-局部最大值"] = localMaxRoots;
//     //
//     //     // ========== 第二步：从根部BFS追踪 ==========
//     //     AddLog("");
//     //     AddLog("========== 第二步：从根部BFS追踪毛发片 ==========");
//     //     
//     //     HashSet<int> visitedVertices = new HashSet<int>();
//     //     int stripIndex = 0;
//     //
//     //     foreach (int rootVert in rootVertices)
//     //     {
//     //         if (visitedVertices.Contains(rootVert))
//     //         {
//     //             AddLog($"根部[{rootVert}] 已被访问，跳过");
//     //             AddExclusionStat("根部已被其他Strip访问");
//     //             continue;
//     //         }
//     //
//     //         AddLog($"");
//     //         AddLog($"--- 从根部顶点[{rootVert}] (V={uvs[rootVert].y:F4}) 开始追踪 Strip #{stripIndex} ---");
//     //
//     //         HairStrip strip = new HairStrip { index = stripIndex };
//     //         HashSet<int> stripVertices = new HashSet<int>();
//     //         HashSet<int> stripTriangleIndices = new HashSet<int>();
//     //         
//     //         // 追踪统计
//     //         int addedCount = 0;
//     //         int skippedVisited = 0;
//     //         int skippedVIncrease = 0;
//     //         int skippedDeltaTooLarge = 0;
//     //
//     //         Queue<int> queue = new Queue<int>();
//     //         queue.Enqueue(rootVert);
//     //
//     //         while (queue.Count > 0)
//     //         {
//     //             int current = queue.Dequeue();
//     //             
//     //             if (visitedVertices.Contains(current))
//     //             {
//     //                 skippedVisited++;
//     //                 continue;
//     //             }
//     //
//     //             visitedVertices.Add(current);
//     //             stripVertices.Add(current);
//     //             addedCount++;
//     //
//     //             if (vertexToTriangles.ContainsKey(current))
//     //             {
//     //                 foreach (int triIdx in vertexToTriangles[current])
//     //                 {
//     //                     stripTriangleIndices.Add(triIdx);
//     //                 }
//     //             }
//     //
//     //             float currentV = uvs[current].y;
//     //             
//     //             // 检查每个邻居
//     //             foreach (int neighbor in adjacency[current])
//     //             {
//     //                 if (visitedVertices.Contains(neighbor))
//     //                 {
//     //                     skippedVisited++;
//     //                     AddLog($"    顶点[{current}] → 邻居[{neighbor}]: ✗ 已访问");
//     //                     AddExclusionStat("邻居已被访问");
//     //                     continue;
//     //                 }
//     //
//     //                 float neighborV = uvs[neighbor].y;
//     //                 float deltaV = Mathf.Abs(neighborV - currentV);
//     //                 
//     //                 // 判断条件
//     //                 bool vNotIncreasing = neighborV <= currentV + 0.02f;
//     //                 bool deltaInRange = deltaV < uvContinuityThreshold;
//     //
//     //                 if (vNotIncreasing && deltaInRange)
//     //                 {
//     //                     queue.Enqueue(neighbor);
//     //                     AddLog($"    顶点[{current}] V={currentV:F4} → 邻居[{neighbor}] V={neighborV:F4}: ✓ 加入队列 (ΔV={deltaV:F4})");
//     //                 }
//     //                 else
//     //                 {
//     //                     // 详细记录排除原因
//     //                     string reason = "";
//     //                     if (!vNotIncreasing)
//     //                     {
//     //                         reason = $"V值增加过多 ({neighborV:F4} > {currentV:F4} + 0.02)";
//     //                         skippedVIncrease++;
//     //                         AddExclusionStat("V值反向增加过多");
//     //                     }
//     //                     else if (!deltaInRange)
//     //                     {
//     //                         reason = $"ΔV超过阈值 ({deltaV:F4} >= {uvContinuityThreshold})";
//     //                         skippedDeltaTooLarge++;
//     //                         AddExclusionStat($"ΔV超过阈值({uvContinuityThreshold})");
//     //                     }
//     //                     
//     //                     AddLog($"    顶点[{current}] V={currentV:F4} → 邻居[{neighbor}] V={neighborV:F4}: ✗ 排除 - {reason}");
//     //                 }
//     //             }
//     //         }
//     //
//     //         // 收集三角形
//     //         foreach (int triIdx in stripTriangleIndices)
//     //         {
//     //             int baseIdx = triIdx * 3;
//     //             int v0 = triangles[baseIdx];
//     //             int v1 = triangles[baseIdx + 1];
//     //             int v2 = triangles[baseIdx + 2];
//     //
//     //             bool allInStrip = stripVertices.Contains(v0) &&
//     //                               stripVertices.Contains(v1) &&
//     //                               stripVertices.Contains(v2);
//     //
//     //             if (allInStrip)
//     //             {
//     //                 strip.triangleIndices.Add(v0);
//     //                 strip.triangleIndices.Add(v1);
//     //                 strip.triangleIndices.Add(v2);
//     //             }
//     //             else
//     //             {
//     //                 // 添加缺失的顶点
//     //                 if (!stripVertices.Contains(v0)) 
//     //                 {
//     //                     stripVertices.Add(v0);
//     //                     AddLog($"    三角形[{triIdx}]: 补充顶点[{v0}] (不在追踪路径上)");
//     //                     AddExclusionStat("三角形补充顶点");
//     //                 }
//     //                 if (!stripVertices.Contains(v1)) 
//     //                 {
//     //                     stripVertices.Add(v1);
//     //                     AddLog($"    三角形[{triIdx}]: 补充顶点[{v1}] (不在追踪路径上)");
//     //                     AddExclusionStat("三角形补充顶点");
//     //                 }
//     //                 if (!stripVertices.Contains(v2)) 
//     //                 {
//     //                     stripVertices.Add(v2);
//     //                     AddLog($"    三角形[{triIdx}]: 补充顶点[{v2}] (不在追踪路径上)");
//     //                     AddExclusionStat("三角形补充顶点");
//     //                 }
//     //                 strip.triangleIndices.Add(v0);
//     //                 strip.triangleIndices.Add(v1);
//     //                 strip.triangleIndices.Add(v2);
//     //             }
//     //         }
//     //
//     //         strip.vertexIndices = stripVertices.ToList();
//     //
//     //         // Strip统计
//     //         AddLog($"  Strip #{stripIndex} 追踪完成:");
//     //         AddLog($"    - 加入顶点: {addedCount}");
//     //         AddLog($"    - 跳过(已访问): {skippedVisited}");
//     //         AddLog($"    - 排除(V增加): {skippedVIncrease}");
//     //         AddLog($"    - 排除(ΔV过大): {skippedDeltaTooLarge}");
//     //         AddLog($"    - 最终顶点数: {strip.vertexIndices.Count}");
//     //         AddLog($"    - 三角形数: {strip.triangleIndices.Count / 3}");
//     //
//     //         // 计算统计
//     //         if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
//     //         {
//     //             strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//     //             strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//     //
//     //             int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//     //             int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//     //
//     //             strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//     //             strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//     //
//     //             hairStrips.Add(strip);
//     //             
//     //             AddLog($"    V值范围: {strip.minV:F4} ~ {strip.maxV:F4} (跨度: {strip.vRange:F4})");
//     //             AddLog($"    ✓ Strip #{stripIndex} 有效，已添加");
//     //             
//     //             stripIndex++;
//     //         }
//     //         else
//     //         {
//     //             AddLog($"    ✗ Strip 无效 (顶点<2 或 三角形<1)，已丢弃");
//     //             AddExclusionStat("Strip无效(顶点或三角形不足)");
//     //         }
//     //     }
//     //
//     //     AddLog("");
//     //     AddLog($"========== 分析完成 ==========");
//     //     AddLog($"有效毛发片: {hairStrips.Count}");
//     //     AddLog($"总访问顶点: {visitedVertices.Count} / {analyzedMesh.vertexCount}");
//     //     
//     //     // 检查未访问的顶点
//     //     int unvisitedCount = analyzedMesh.vertexCount - visitedVertices.Count;
//     //     if (unvisitedCount > 0)
//     //     {
//     //         AddLog($"未访问顶点: {unvisitedCount}");
//     //         AddExclusionStat($"顶点未被任何Strip访问");
//     //         exclusionStats[$"顶点未被任何Strip访问"] = unvisitedCount;
//     //         // 详细分析未访问顶点的原因
//     //         AnalyzeUnvisitedVertices(visitedVertices, adjacency, uvs);
//     //     }
//     // }
//     // /// <summary>
//     // /// 【新增】分析未访问顶点的具体原因
//     // /// </summary>
//     // private void AnalyzeUnvisitedVertices(HashSet<int> visitedVertices,
//     //     Dictionary<int, HashSet<int>> adjacency, Vector2[] uvs)
//     // {
//     //     AddLog("");
//     //     AddLog("---------- 未访问顶点详细分析 ----------");
//     //
//     //     int noNeighbors = 0; // 孤立顶点
//     //     int notConnectedToRoot = 0; // 与根部不连通
//     //     int uvJumpTooLarge = 0; // UV跳变太大
//     //
//     //     int loggedCount = 0;
//     //     int maxDetailedLogs = 50; // 限制详细日志数量
//     //
//     //     for (int i = 0; i < uvs.Length; i++)
//     //     {
//     //         if (visitedVertices.Contains(i))
//     //             continue;
//     //
//     //         string reason = "";
//     //
//     //         // 检查原因
//     //         if (!adjacency.ContainsKey(i) || adjacency[i].Count == 0)
//     //         {
//     //             noNeighbors++;
//     //             reason = "孤立顶点（无邻居）";
//     //         }
//     //         else
//     //         {
//     //             // 检查是否有已访问的邻居
//     //             bool hasVisitedNeighbor = adjacency[i].Any(n => visitedVertices.Contains(n));
//     //
//     //             if (!hasVisitedNeighbor)
//     //             {
//     //                 notConnectedToRoot++;
//     //                 reason = "与已访问区域不连通";
//     //             }
//     //             else
//     //             {
//     //                 // 有已访问的邻居，但自己没被访问 → UV跳变太大
//     //                 uvJumpTooLarge++;
//     //
//     //                 // 找出是哪个邻居拒绝了它
//     //                 foreach (int neighbor in adjacency[i])
//     //                 {
//     //                     if (visitedVertices.Contains(neighbor))
//     //                     {
//     //                         float neighborV = uvs[neighbor].y;
//     //                         float myV = uvs[i].y;
//     //                         float deltaV = Mathf.Abs(myV - neighborV);
//     //
//     //                         bool vIncreased = myV > neighborV + 0.02f;
//     //                         bool deltaTooLarge = deltaV >= uvContinuityThreshold;
//     //
//     //                         if (vIncreased)
//     //                             reason = $"V值反向增加 (我:{myV:F4} > 邻居:{neighborV:F4}+0.02)";
//     //                         else if (deltaTooLarge)
//     //                             reason = $"ΔV超阈值 (ΔV={deltaV:F4} >= {uvContinuityThreshold})";
//     //                         else
//     //                             reason = $"被邻居[{neighbor}]拒绝 (原因不明)";
//     //
//     //                         break;
//     //                     }
//     //                 }
//     //             }
//     //         }
//     //
//     //         // 限制日志输出数量
//     //         if (loggedCount < maxDetailedLogs)
//     //         {
//     //             AddLog($"  顶点[{i}] V={uvs[i].y:F4}: {reason}");
//     //             loggedCount++;
//     //         }
//     //     }
//     //
//     //     if (uvs.Length - visitedVertices.Count > maxDetailedLogs)
//     //     {
//     //         AddLog($"  ... 还有 {uvs.Length - visitedVertices.Count - maxDetailedLogs} 个未显示");
//     //     }
//     //
//     //     AddLog($"");
//     //     AddLog($"未访问顶点原因汇总:");
//     //     AddLog($"  - 孤立顶点(无邻居): {noNeighbors}");
//     //     AddLog($"  - 与已访问区域不连通: {notConnectedToRoot}");
//     //     AddLog($"  - UV跳变被拒绝: {uvJumpTooLarge}");
//     //
//     //     // 更新统计字典
//     //     if (noNeighbors > 0)
//     //         exclusionStats["未访问-孤立顶点"] = noNeighbors;
//     //     if (notConnectedToRoot > 0)
//     //         exclusionStats["未访问-与根部不连通"] = notConnectedToRoot;
//     //     if (uvJumpTooLarge > 0)
//     //         exclusionStats["未访问-UV跳变被拒绝"] = uvJumpTooLarge;
//     // }
//     //
//
//     /// <summary>
//     /// 【改进版】基于UV分析 - 先分组再找根部（带详细日志）
//     /// </summary>
//     private void AnalyzeByUV()
//     {
//         Vector2[] uvs = analyzedMesh.uv;
//         Vector3[] vertices = analyzedMesh.vertices;
//         int[] triangles = analyzedMesh.triangles;
//
//         if (uvs == null || uvs.Length == 0)
//         {
//             EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
//             return;
//         }
//
//         AddLog("========== 改进版UV分析：先分组再找根部 ==========");
//         AddLog($"总顶点数: {analyzedMesh.vertexCount}");
//         AddLog($"总三角形数: {triangles.Length / 3}");
//         AddLog($"全局V值范围: {globalMinV:F4} ~ {globalMaxV:F4} (Range={globalVRange:F4})");
//
//         // ========== 第一步：按几何连通性分组 ==========
//         AddLog("");
//         AddLog("========== 第一步：几何连通性分组 ==========");
//
//         var geometryGroups = FindConnectedComponents(triangles, analyzedMesh.vertexCount);
//         AddLog($"几何分组完成，共 {geometryGroups.Count} 个独立组");
//
//         // 统计组大小分布
//         var groupSizes = geometryGroups.Select(g => g.Count).OrderByDescending(x => x).ToList();
//         if (groupSizes.Count > 0)
//         {
//             AddLog($"组大小范围: {groupSizes.Min()} ~ {groupSizes.Max()} (平均: {groupSizes.Average():F1})");
//
//             // 组大小分布直方图
//             var sizeDistribution = groupSizes.GroupBy(s =>
//             {
//                 if (s < 3) return "<3";
//                 if (s < 6) return "3-5";
//                 if (s < 10) return "6-9";
//                 if (s < 20) return "10-19";
//                 if (s < 50) return "20-49";
//                 return "50+";
//             }).ToDictionary(g => g.Key, g => g.Count());
//
//             AddLog("组大小分布:");
//             foreach (var kvp in sizeDistribution.OrderBy(x => x.Key))
//             {
//                 AddLog($"  {kvp.Key} 顶点: {kvp.Value} 组");
//             }
//         }
//
//         // ========== 第二步：在每个组内找根部并构建Strip ==========
//         AddLog("");
//         AddLog("========== 第二步：组内找根部并构建Strip ==========");
//
//         var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
//         var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
//
//         int stripIndex = 0;
//         int skippedTooSmall = 0;
//         int skippedNoVRange = 0;
//         int skippedNoTriangles = 0;
//
//         int loggedGroups = 0;
//         int maxGroupLogs = 100; // 限制详细日志的组数量
//
//         for (int groupIdx = 0; groupIdx < geometryGroups.Count; groupIdx++)
//         {
//             var group = geometryGroups[groupIdx];
//             bool shouldLog = loggedGroups < maxGroupLogs;
//
//             // 跳过太小的组
//             if (group.Count < 3)
//             {
//                 skippedTooSmall++;
//                 if (shouldLog)
//                 {
//                     AddLog($"");
//                     AddLog($"--- 组 #{groupIdx} ---");
//                     AddLog($"  顶点数: {group.Count}");
//                     AddLog($"  ✗ 跳过原因: 顶点数太少 (<3)");
//                     loggedGroups++;
//                 }
//
//                 continue;
//             }
//
//             // 在组内找V值最大的顶点作为根部
//             int rootVert = -1;
//             float maxV = float.MinValue;
//             int tipVert = -1;
//             float minV = float.MaxValue;
//
//             foreach (int vertIdx in group)
//             {
//                 float v = uvs[vertIdx].y;
//                 if (v > maxV)
//                 {
//                     maxV = v;
//                     rootVert = vertIdx;
//                 }
//
//                 if (v < minV)
//                 {
//                     minV = v;
//                     tipVert = vertIdx;
//                 }
//             }
//
//             float groupVRange = maxV - minV;
//
//             // 详细日志
//             if (shouldLog)
//             {
//                 AddLog($"");
//                 AddLog($"--- 组 #{groupIdx} ---");
//                 AddLog($"  顶点数: {group.Count}");
//                 AddLog($"  顶点列表: [{string.Join(", ", group.Take(20))}{(group.Count > 20 ? "..." : "")}]");
//                 AddLog($"  根部顶点: [{rootVert}] V={maxV:F4}");
//                 AddLog($"  尖端顶点: [{tipVert}] V={minV:F4}");
//                 AddLog($"  V值范围: {minV:F4} ~ {maxV:F4} (跨度={groupVRange:F4})");
//             }
//
//             // 跳过V值范围太小的组
//             if (groupVRange < 0.01f)
//             {
//                 skippedNoVRange++;
//                 if (shouldLog)
//                 {
//                     AddLog($"  ✗ 跳过原因: V值跨度太小 ({groupVRange:F4} < 0.01)");
//                     loggedGroups++;
//                 }
//
//                 continue;
//             }
//
//             // 创建Strip
//             HairStrip strip = new HairStrip { index = stripIndex };
//
//             // 使用整个组的顶点
//             strip.vertexIndices = group.ToList();
//
//             // 收集该组的所有三角形
//             HashSet<int> groupTriangles = new HashSet<int>();
//             foreach (int vertIdx in group)
//             {
//                 if (vertexToTriangles.ContainsKey(vertIdx))
//                 {
//                     foreach (int triIdx in vertexToTriangles[vertIdx])
//                     {
//                         groupTriangles.Add(triIdx);
//                     }
//                 }
//             }
//
//             if (shouldLog)
//             {
//                 AddLog($"  关联三角形数: {groupTriangles.Count}");
//             }
//
//             // 添加三角形（只添加所有顶点都在组内的三角形）
//             int validTriangles = 0;
//             int invalidTriangles = 0;
//
//             foreach (int triIdx in groupTriangles)
//             {
//                 int baseIdx = triIdx * 3;
//                 int v0 = triangles[baseIdx];
//                 int v1 = triangles[baseIdx + 1];
//                 int v2 = triangles[baseIdx + 2];
//
//                 bool allInGroup = group.Contains(v0) && group.Contains(v1) && group.Contains(v2);
//
//                 if (allInGroup)
//                 {
//                     strip.triangleIndices.Add(v0);
//                     strip.triangleIndices.Add(v1);
//                     strip.triangleIndices.Add(v2);
//                     validTriangles++;
//                 }
//                 else
//                 {
//                     invalidTriangles++;
//                     if (shouldLog && invalidTriangles <= 3)
//                     {
//                         AddLog($"    跳过三角形[{triIdx}]: ({v0},{v1},{v2}) - 不是所有顶点都在组内");
//                     }
//                 }
//             }
//
//             if (shouldLog && invalidTriangles > 3)
//             {
//                 AddLog($"    ... 还有 {invalidTriangles - 3} 个三角形被跳过");
//             }
//
//             // 设置统计信息
//             strip.minV = minV;
//             strip.maxV = maxV;
//             strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootVert]);
//             strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipVert]);
//
//             // 验证Strip有效性
//             if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
//             {
//                 hairStrips.Add(strip);
//
//                 if (shouldLog)
//                 {
//                     AddLog($"  有效三角形: {validTriangles}");
//                     AddLog($"  ✓ Strip #{stripIndex} 创建成功");
//                     AddLog($"    - 顶点数: {strip.vertexIndices.Count}");
//                     AddLog($"    - 三角形数: {strip.triangleIndices.Count / 3}");
//                     AddLog($"    - 根部位置: {strip.rootPosition}");
//                     AddLog($"    - 尖端位置: {strip.tipPosition}");
//                     loggedGroups++;
//                 }
//
//                 stripIndex++;
//             }
//             else
//             {
//                 if (strip.triangleIndices.Count < 3)
//                 {
//                     skippedNoTriangles++;
//                     if (shouldLog)
//                     {
//                         AddLog($"  ✗ 跳过原因: 有效三角形不足 ({strip.triangleIndices.Count / 3} < 1)");
//                         loggedGroups++;
//                     }
//                 }
//                 else
//                 {
//                     if (shouldLog)
//                     {
//                         AddLog($"  ✗ 跳过原因: 顶点数不足 ({strip.vertexIndices.Count} < 2)");
//                         loggedGroups++;
//                     }
//                 }
//             }
//         }
//
//         if (geometryGroups.Count > maxGroupLogs)
//         {
//             AddLog($"");
//             AddLog($"... 还有 {geometryGroups.Count - maxGroupLogs} 个组未显示详细日志");
//         }
//
//         // ========== 统计汇总 ==========
//         AddLog("");
//         AddLog("========== 分析完成 - 统计汇总 ==========");
//         AddLog($"几何组总数: {geometryGroups.Count}");
//         AddLog($"");
//         AddLog("跳过的组:");
//         AddLog($"  - 顶点太少(<3): {skippedTooSmall}");
//         AddLog($"  - V值跨度太小(<0.01): {skippedNoVRange}");
//         AddLog($"  - 有效三角形不足: {skippedNoTriangles}");
//         AddLog($"  - 跳过总计: {skippedTooSmall + skippedNoVRange + skippedNoTriangles}");
//         AddLog($"");
//         AddLog($"有效毛发片: {hairStrips.Count}");
//
//         if (hairStrips.Count > 0)
//         {
//             AddLog($"");
//             AddLog("毛发片统计:");
//             var stripVertCounts = hairStrips.Select(s => s.vertexCount).ToList();
//             var stripTriCounts = hairStrips.Select(s => s.triangleCount).ToList();
//             var stripVRanges = hairStrips.Select(s => s.vRange).ToList();
//             var stripMaxVs = hairStrips.Select(s => s.maxV).ToList();
//             var stripMinVs = hairStrips.Select(s => s.minV).ToList();
//
//             AddLog($"  顶点数: {stripVertCounts.Min()} ~ {stripVertCounts.Max()} (平均: {stripVertCounts.Average():F1})");
//             AddLog($"  三角形数: {stripTriCounts.Min()} ~ {stripTriCounts.Max()} (平均: {stripTriCounts.Average():F1})");
//             AddLog($"  V值跨度: {stripVRanges.Min():F4} ~ {stripVRanges.Max():F4} (平均: {stripVRanges.Average():F4})");
//             AddLog($"  根部V值: {stripMaxVs.Min():F4} ~ {stripMaxVs.Max():F4} (平均: {stripMaxVs.Average():F4})");
//             AddLog($"  尖端V值: {stripMinVs.Min():F4} ~ {stripMinVs.Max():F4} (平均: {stripMinVs.Average():F4})");
//         }
//
//         // 更新排除统计字典
//         exclusionStats.Clear();
//         if (skippedTooSmall > 0)
//             exclusionStats["组太小(<3顶点)"] = skippedTooSmall;
//         if (skippedNoVRange > 0)
//             exclusionStats["组V值跨度太小(<0.01)"] = skippedNoVRange;
//         if (skippedNoTriangles > 0)
//             exclusionStats["有效三角形不足"] = skippedNoTriangles;
//         exclusionStats["有效毛发片"] = hairStrips.Count;
//         exclusionStats["几何组总数"] = geometryGroups.Count;
//     }
//
//     /// <summary>
//     /// 【新增】查找几何连通分量（带详细日志）
//     /// </summary>
//     private List<HashSet<int>> FindConnectedComponents(int[] triangles, int vertexCount)
//     {
//         AddLog("开始查找几何连通分量...");
//
//         // 构建邻接表
//         var adjacency = new Dictionary<int, HashSet<int>>();
//         for (int i = 0; i < vertexCount; i++)
//             adjacency[i] = new HashSet<int>();
//
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
//             adjacency[v0].Add(v1);
//             adjacency[v0].Add(v2);
//             adjacency[v1].Add(v0);
//             adjacency[v1].Add(v2);
//             adjacency[v2].Add(v0);
//             adjacency[v2].Add(v1);
//         }
//
//         AddLog($"邻接表构建完成");
//
//         // 统计邻居数量分布
//         var neighborCounts = adjacency.Values.Select(s => s.Count).ToList();
//         int isolated = neighborCounts.Count(c => c == 0);
//         int hasNeighbors = neighborCounts.Count(c => c > 0);
//
//         AddLog($"顶点邻居统计:");
//         AddLog($"  - 有邻居的顶点: {hasNeighbors}");
//         AddLog($"  - 孤立顶点(无邻居): {isolated}");
//         if (hasNeighbors > 0)
//         {
//             var nonZeroCounts = neighborCounts.Where(c => c > 0).ToList();
//             AddLog($"  - 邻居数范围: {nonZeroCounts.Min()} ~ {nonZeroCounts.Max()} (平均: {nonZeroCounts.Average():F1})");
//         }
//
//         // BFS找连通分量
//         var visited = new HashSet<int>();
//         var components = new List<HashSet<int>>();
//         int isolatedSkipped = 0;
//
//         for (int i = 0; i < vertexCount; i++)
//         {
//             if (visited.Contains(i))
//                 continue;
//
//             // 跳过没有邻居的孤立顶点
//             if (adjacency[i].Count == 0)
//             {
//                 visited.Add(i);
//                 isolatedSkipped++;
//                 continue;
//             }
//
//             // BFS遍历这个连通分量
//             var component = new HashSet<int>();
//             var queue = new Queue<int>();
//             queue.Enqueue(i);
//
//             while (queue.Count > 0)
//             {
//                 int current = queue.Dequeue();
//                 if (visited.Contains(current))
//                     continue;
//
//                 visited.Add(current);
//                 component.Add(current);
//
//                 foreach (int neighbor in adjacency[current])
//                 {
//                     if (!visited.Contains(neighbor))
//                         queue.Enqueue(neighbor);
//                 }
//             }
//
//             if (component.Count > 0)
//                 components.Add(component);
//         }
//
//         AddLog($"");
//         AddLog($"连通分量查找完成:");
//         AddLog($"  - 找到的连通分量: {components.Count}");
//         AddLog($"  - 跳过的孤立顶点: {isolatedSkipped}");
//         AddLog($"  - 已访问顶点总数: {visited.Count}");
//
//         if (isolatedSkipped > 0)
//         {
//             AddExclusionStat("孤立顶点(无邻居)");
//             exclusionStats["孤立顶点(无邻居)"] = isolatedSkipped;
//         }
//
//         return components;
//     }
//
//
//
//     /// <summary>
//     /// 基于连通分量分析
//     /// </summary>
//     private void AnalyzeByConnectedComponent()
//     {
//         int[] triangles = analyzedMesh.triangles;
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         
//         var edgeTriangles = new Dictionary<Edge, List<int>>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIndex = i / 3;
//             AddEdgeTriangle(edgeTriangles, triangles[i], triangles[i + 1], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 1], triangles[i + 2], triIndex);
//             AddEdgeTriangle(edgeTriangles, triangles[i + 2], triangles[i], triIndex);
//         }
//         
//         int totalTriangles = triangles.Length / 3;
//         UnionFind uf = new UnionFind(totalTriangles);
//         
//         foreach (var kvp in edgeTriangles)
//         {
//             var tris = kvp.Value;
//             for (int i = 0; i < tris.Count - 1; i++)
//             {
//                 for (int j = i + 1; j < tris.Count; j++)
//                 {
//                     uf.Union(tris[i], tris[j]);
//                 }
//             }
//         }
//         
//         var groups = new Dictionary<int, List<int>>();
//         for (int i = 0; i < totalTriangles; i++)
//         {
//             int root = uf.Find(i);
//             if (!groups.ContainsKey(root))
//                 groups[root] = new List<int>();
//             groups[root].Add(i);
//         }
//         
//         int stripIndex = 0;
//         foreach (var group in groups.Values)
//         {
//             HairStrip strip = new HairStrip { index = stripIndex++ };
//             HashSet<int> vertSet = new HashSet<int>();
//             
//             foreach (int triIdx in group)
//             {
//                 int baseIdx = triIdx * 3;
//                 strip.triangleIndices.Add(triangles[baseIdx]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 1]);
//                 strip.triangleIndices.Add(triangles[baseIdx + 2]);
//                 
//                 vertSet.Add(triangles[baseIdx]);
//                 vertSet.Add(triangles[baseIdx + 1]);
//                 vertSet.Add(triangles[baseIdx + 2]);
//             }
//             
//             strip.vertexIndices = vertSet.ToList();
//             
//             if (uvs != null && uvs.Length > 0 && strip.vertexIndices.Count > 0)
//             {
//                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
//                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
//                 
//                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
//                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
//                 
//                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
//                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
//             }
//             
//             hairStrips.Add(strip);
//         }
//     }
//
//     /// <summary>
//     /// Scene视图绘制
//     /// </summary>
//     private void OnSceneGUI(SceneView sceneView)
//     {
//         if (!analysisComplete || targetObject == null || hairStrips.Count == 0 || analyzedMesh == null)
//             return;
//         
//         Vector3[] vertices = analyzedMesh.vertices;
//         Vector2[] uvs = analyzedMesh.uv;
//         Transform transform = targetObject.transform;
//         
//         Handles.matrix = Matrix4x4.identity;
//         
//         if (showAllStrips)
//         {
//             foreach (var strip in hairStrips)
//             {
//                 float alpha = strip.index == currentStripIndex ? 1f : 0.2f;
//                 DrawStrip(strip, vertices, uvs, transform, alpha);
//             }
//         }
//         else if (currentStripIndex < hairStrips.Count)
//         {
//             DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
//         }
//     }
//
//     private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
//     {
//         Color stripColor = strip.debugColor;
//         
//         // 绘制三角形面
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawAAConvexPolygon(v0, v1, v2);
//         }
//         
//         // 绘制边
//         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.8f);
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
//             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
//             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
//             Handles.DrawLine(v0, v1);
//             Handles.DrawLine(v1, v2);
//             Handles.DrawLine(v2, v0);
//         }
//         
//         // 绘制顶点（使用当前选择的UV差值模式着色）
//         foreach (int vertIdx in strip.vertexIndices)
//         {
//             Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
//             float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;
//             
//             // 使用当前模式计算差值
//             float diff = CalculateUVDifference(vValue, strip);
//             
//             // 根据模式决定颜色映射
//             Color vertColor;
//             // if (uvDifferenceMode == UVDifferenceMode.GlobalV)
//             // {
//             //     // GlobalV模式：根部=0(绿色), 尖端=1(红色)
//             //     vertColor = Color.Lerp(Color.green, Color.red, diff);
//             // }
//             // else
//             // {
//                 // 其他模式：根部=1(绿色), 尖端=0(红色)
//                 vertColor = Color.Lerp(Color.red, Color.green, diff);
//             //}
//             vertColor.a = alpha;
//             
//             Handles.color = vertColor;
//             Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);
//             
//             // 标签
//             if ((showVertexLabels || showUVInfo) && alpha > 0.5f)
//             {
//                 string label = "";
//                 if (showVertexLabels) label += $"[{vertIdx}]";
//                 if (showUVInfo) label += $" V:{vValue:F3} D:{diff:F2}";
//                 Handles.Label(worldPos + Vector3.up * vertexSphereSize * 1.5f, label, EditorStyles.miniLabel);
//             }
//         }
//         
//         // 绘制根部和尖端标记
//         if (showRootTipMarkers && alpha > 0.5f)
//         {
//             float rootDiff = CalculateUVDifference(strip.maxV, strip);
//             float tipDiff = CalculateUVDifference(strip.minV, strip);
//             
//             // ROOT标记 - 绿色大球
//             Handles.color = Color.green;
//             Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.rootPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"ROOT\nV={strip.maxV:F3}\nDiff={rootDiff:F3}", EditorStyles.whiteBoldLabel);
//             
//             // TIP标记 - 红色大球
//             Handles.color = Color.red;
//             Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
//             Handles.Label(strip.tipPosition + Vector3.up * vertexSphereSize * 3f, 
//                 $"TIP\nV={strip.minV:F3}\nDiff={tipDiff:F3}", EditorStyles.whiteBoldLabel);
//             
//             // 连接线
//             Handles.color = Color.yellow;
//             Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 3f);
//         }
//     }
//
//     private void FocusOnStrip(int index)
//     {
//         if (index >= hairStrips.Count) return;
//         
//         var strip = hairStrips[index];
//         Vector3 center = (strip.rootPosition + strip.tipPosition) / 2f;
//         float size = Mathf.Max(Vector3.Distance(strip.rootPosition, strip.tipPosition) * 3f, 0.1f);
//         
//         SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, size);
//         SceneView.RepaintAll();
//     }
//
//     /// <summary>
//     /// 生成带UV差值的Mesh
//     /// </summary>
//     private void GenerateMeshWithUVDifference()
//     {
//         Mesh newMesh = Instantiate(analyzedMesh);
//         newMesh.name = analyzedMesh.name + $"_UVDiff_{uvDifferenceMode}";
//         
//         Vector2[] uvs = newMesh.uv;
//         Color[] colors = new Color[newMesh.vertexCount];
//         
//         // 初始化
//         for (int i = 0; i < colors.Length; i++)
//             colors[i] = new Color(1, 1, 0, 1);
//         
//         // 创建顶点到毛发片的映射
//         Dictionary<int, HairStrip> vertexToStrip = new Dictionary<int, HairStrip>();
//         foreach (var strip in hairStrips)
//         {
//             foreach (int vertIdx in strip.vertexIndices)
//             {
//                 if (!vertexToStrip.ContainsKey(vertIdx))
//                 {
//                     vertexToStrip[vertIdx] = strip;
//                 }
//             }
//         }
//         
//         // 计算每个顶点的差值
//         for (int i = 0; i < colors.Length; i++)
//         {
//             float v = uvs[i].y;
//             float diff = 0f;
//             
//             if (vertexToStrip.ContainsKey(i))
//             {
//                 HairStrip strip = vertexToStrip[i];
//                 diff = CalculateUVDifference(v, strip);
//             }
//             else
//             {
//                 // 对于未分配到毛发片的顶点，使用全局归一化
//                 diff = globalVRange > 0.001f ? (v - globalMinV) / globalVRange : 0f;
//             }
//             
//             colors[i].b = diff; // 存储到B通道
//         }
//         
//         newMesh.colors = colors;
//         
//         // 应用并保存
//         ApplyMesh(newMesh);
//         
//         string path = EditorUtility.SaveFilePanelInProject(
//             "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");
//         
//         if (!string.IsNullOrEmpty(path))
//         {
//             AssetDatabase.CreateAsset(newMesh, path);
//             AssetDatabase.SaveAssets();
//             Debug.Log($"✓ Mesh已保存: {path}");
//             Debug.Log($"UV差值模式: {uvDifferenceMode}");
//             Debug.Log("UV差值已存储到顶点颜色B通道");
//         }
//     }
//     
//     /// <summary>
//     /// 导出单个毛发片
//     /// </summary>
//     private void ExportSingleStrip(HairStrip strip)
//     {
//         if (strip == null)
//         {
//             EditorUtility.DisplayDialog("错误", "毛发片数据为空", "确定");
//             return;
//         }
//     
//         if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 顶点数不足 ({strip.vertexIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//         {
//             EditorUtility.DisplayDialog("错误", $"毛发片 #{strip.index} 三角形数不足 ({strip.triangleIndices?.Count ?? 0})", "确定");
//             return;
//         }
//     
//         try
//         {
//             Mesh mesh = CreateMeshFromStrip(strip);
//         
//             if (mesh == null || mesh.vertexCount == 0)
//             {
//                 EditorUtility.DisplayDialog("错误", "生成Mesh失败", "确定");
//                 return;
//             }
//         
//             string path = EditorUtility.SaveFilePanelInProject(
//                 "保存毛发片", 
//                 $"HairStrip_{strip.index}_{uvDifferenceMode}", 
//                 "asset", 
//                 "选择保存位置");
//         
//             if (!string.IsNullOrEmpty(path))
//             {
//                 if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                 {
//                     AssetDatabase.DeleteAsset(path);
//                 }
//             
//                 AssetDatabase.CreateAsset(mesh, path);
//                 AssetDatabase.SaveAssets();
//             
//                 Debug.Log($"✓ 毛发片 #{strip.index} 已导出到: {path}");
//                 Debug.Log($"  UV差值模式: {uvDifferenceMode}");
//                 Debug.Log($"  顶点数: {mesh.vertexCount}, 三角形数: {mesh.triangles.Length / 3}");
//             }
//         }
//         catch (System.Exception e)
//         {
//             EditorUtility.DisplayDialog("导出失败", $"错误: {e.Message}", "确定");
//             Debug.LogError($"导出毛发片 #{strip.index} 失败: {e}");
//         }
//     }
//
//     /// <summary>
//     /// 导出所有毛发片
//     /// </summary>
//     private void ExportAllStrips()
//     {
//         string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
//         if (string.IsNullOrEmpty(folder)) return;
//
//         if (folder.StartsWith(Application.dataPath))
//         {
//             folder = "Assets" + folder.Substring(Application.dataPath.Length);
//         }
//
//         if (!AssetDatabase.IsValidFolder(folder))
//         {
//             Debug.LogError($"无效的文件夹路径: {folder}");
//             return;
//         }
//
//         int successCount = 0;
//         int failCount = 0;
//         List<string> failedStrips = new List<string>();
//
//         try
//         {
//             for (int i = 0; i < hairStrips.Count; i++)
//             {
//                 var strip = hairStrips[i];
//
//                 bool cancel = EditorUtility.DisplayCancelableProgressBar(
//                     "导出毛发片",
//                     $"正在导出 {i + 1}/{hairStrips.Count}: HairStrip_{strip.index}",
//                     (float)i / hairStrips.Count);
//
//                 if (cancel)
//                 {
//                     Debug.Log("用户取消导出");
//                     break;
//                 }
//
//                 try
//                 {
//                     if (strip.vertexIndices == null || strip.vertexIndices.Count < 2)
//                     {
//                         failedStrips.Add($"#{strip.index}: 顶点数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     if (strip.triangleIndices == null || strip.triangleIndices.Count < 3)
//                     {
//                         failedStrips.Add($"#{strip.index}: 三角形数不足");
//                         failCount++;
//                         continue;
//                     }
//
//                     Mesh mesh = CreateMeshFromStrip(strip);
//
//                     if (mesh != null && mesh.vertexCount > 0)
//                     {
//                         string path = $"{folder}/HairStrip_{strip.index}.asset";
//
//                         if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
//                         {
//                             AssetDatabase.DeleteAsset(path);
//                         }
//
//                         AssetDatabase.CreateAsset(mesh, path);
//                         successCount++;
//                     }
//                     else
//                     {
//                         failedStrips.Add($"#{strip.index}: 生成Mesh失败");
//                         failCount++;
//                     }
//                 }
//                 catch (System.Exception e)
//                 {
//                     failedStrips.Add($"#{strip.index}: {e.Message}");
//                     failCount++;
//                     Debug.LogError($"导出毛发片 #{strip.index} 失败: {e.Message}");
//                 }
//             }
//         }
//         finally
//         {
//             EditorUtility.ClearProgressBar();
//         }
//
//         AssetDatabase.SaveAssets();
//         AssetDatabase.Refresh();
//
//         string message = $"导出完成！\n成功: {successCount}\n失败: {failCount}\nUV差值模式: {uvDifferenceMode}";
//
//         if (failedStrips.Count > 0)
//         {
//             message += $"\n\n失败详情:\n{string.Join("\n", failedStrips.Take(10))}";
//             if (failedStrips.Count > 10)
//             {
//                 message += $"\n... 还有 {failedStrips.Count - 10} 个";
//             }
//         }
//
//         EditorUtility.DisplayDialog("导出结果", message, "确定");
//
//         Debug.Log($"✓ 毛发片导出完成: 成功 {successCount}, 失败 {failCount}, 保存到 {folder}");
//     }
//
//     private void ExportAnalysisReport()
//     {
//         string path = EditorUtility.SaveFilePanel("保存分析报告", "", "HairAnalysisReport", "txt");
//         if (string.IsNullOrEmpty(path)) return;
//         
//         var sb = new System.Text.StringBuilder();
//         sb.AppendLine("========== 毛发分析报告 ==========");
//         sb.AppendLine($"物体: {targetObject.name}");
//         sb.AppendLine($"Mesh: {analyzedMesh.name}");
//         sb.AppendLine($"总顶点数: {analyzedMesh.vertexCount}");
//         sb.AppendLine($"总三角形数: {analyzedMesh.triangles.Length / 3}");
//         sb.AppendLine($"识别毛发片数: {hairStrips.Count}");
//         sb.AppendLine();
//         sb.AppendLine("---------- 全局UV统计 ----------");
//         sb.AppendLine($"全局 Min V: {globalMinV:F4}");
//         sb.AppendLine($"全局 Max V: {globalMaxV:F4}");
//         sb.AppendLine($"全局 V Range: {globalVRange:F4}");
//         sb.AppendLine();
//         sb.AppendLine($"当前UV差值模式: {uvDifferenceMode}");
//         sb.AppendLine();
//         sb.AppendLine("UV规则: ROOT(根部)=V值最大, TIP(尖端)=V值最小");
//         sb.AppendLine();
//         sb.AppendLine("---------- UV差值计算公式 ----------");
//         switch (uvDifferenceMode)
//         {
//             case UVDifferenceMode.PerStrip:
//                 sb.AppendLine("PerStrip: diff = (V - 片内minV) / 片内vRange");
//                 sb.AppendLine("根部=1, 尖端=0");
//                 break;
//             case UVDifferenceMode.GlobalV:
//                 sb.AppendLine("GlobalV: diff = (全局maxV - 片内maxV) ");
//                 sb.AppendLine("根部=1, 尖端=0");
//                 break;
//             case UVDifferenceMode.GlobalRange:
//                 sb.AppendLine("GlobalRange: diff = (V - 全局minV) / 全局vRange");
//                 sb.AppendLine("根部=1, 尖端=0");
//                 break;
//         }
//         sb.AppendLine();
//         
//         // 添加排除统计
//         if (exclusionStats.Count > 0)
//         {
//             sb.AppendLine("---------- 排除统计 ----------");
//             foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
//             {
//                 sb.AppendLine($"{kvp.Key}: {kvp.Value}");
//             }
//             sb.AppendLine();
//         }
//         
//         sb.AppendLine("---------- 各毛发片详情 ----------");
//         
//         foreach (var strip in hairStrips)
//         {
//             float rootDiff = CalculateUVDifference(strip.maxV, strip);
//             float tipDiff = CalculateUVDifference(strip.minV, strip);
//             
//             sb.AppendLine($"\n毛发片 #{strip.index}:");
//             sb.AppendLine($"  顶点数: {strip.vertexCount}");
//             sb.AppendLine($"  三角形数: {strip.triangleCount}");
//             sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4}");
//             sb.AppendLine($"  V值跨度: {strip.vRange:F4}");
//             sb.AppendLine($"  根部差值: {rootDiff:F4}");
//             sb.AppendLine($"  尖端差值: {tipDiff:F4}");
//             sb.AppendLine($"  顶点索引: {string.Join(",", strip.vertexIndices.Take(30))}{(strip.vertexIndices.Count > 30 ? "..." : "")}");
//         }
//         
//         System.IO.File.WriteAllText(path, sb.ToString());
//         Debug.Log($"✓ 报告已保存: {path}");
//     }
//
//     /// <summary>
//     /// 从毛发片创建独立Mesh
//     /// </summary>
//     private Mesh CreateMeshFromStrip(HairStrip strip)
//     {
//         Vector3[] origVerts = analyzedMesh.vertices;
//         Vector2[] origUVs = analyzedMesh.uv;
//         Vector3[] origNormals = analyzedMesh.normals;
//         Color[] origColors = analyzedMesh.colors;
//
//         HashSet<int> allVertices = new HashSet<int>(strip.vertexIndices);
//
//         for (int i = 0; i < strip.triangleIndices.Count; i++)
//         {
//             int vertIdx = strip.triangleIndices[i];
//             if (!allVertices.Contains(vertIdx))
//             {
//                 allVertices.Add(vertIdx);
//             }
//         }
//
//         List<int> finalVertexList = allVertices.ToList();
//
//         Dictionary<int, int> remap = new Dictionary<int, int>();
//         for (int i = 0; i < finalVertexList.Count; i++)
//         {
//             remap[finalVertexList[i]] = i;
//         }
//
//         int vertCount = finalVertexList.Count;
//         Vector3[] newVerts = new Vector3[vertCount];
//         Vector2[] newUVs = new Vector2[vertCount];
//         Vector3[] newNormals = new Vector3[vertCount];
//         Color[] newColors = new Color[vertCount];
//
//         for (int i = 0; i < vertCount; i++)
//         {
//             int origIdx = finalVertexList[i];
//
//             newVerts[i] = origVerts[origIdx];
//
//             newUVs[i] = (origUVs != null && origIdx < origUVs.Length)
//                 ? origUVs[origIdx]
//                 : Vector2.zero;
//
//             newNormals[i] = (origNormals != null && origIdx < origNormals.Length)
//                 ? origNormals[origIdx]
//                 : Vector3.up;
//
//             newColors[i] = (origColors != null && origIdx < origColors.Length)
//                 ? origColors[origIdx]
//                 : Color.white;
//         }
//
//         List<int> newTriangles = new List<int>();
//         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
//         {
//             if (i + 2 < strip.triangleIndices.Count)
//             {
//                 int idx0 = strip.triangleIndices[i];
//                 int idx1 = strip.triangleIndices[i + 1];
//                 int idx2 = strip.triangleIndices[i + 2];
//
//                 if (remap.ContainsKey(idx0) && remap.ContainsKey(idx1) && remap.ContainsKey(idx2))
//                 {
//                     newTriangles.Add(remap[idx0]);
//                     newTriangles.Add(remap[idx1]);
//                     newTriangles.Add(remap[idx2]);
//                 }
//             }
//         }
//
//         // 使用当前选择的UV差值模式计算差值
//         for (int i = 0; i < vertCount; i++)
//         {
//             float v = newUVs[i].y;
//             float diff = CalculateUVDifference(v, strip);
//             newColors[i].b = diff;
//         }
//
//         Mesh mesh = new Mesh();
//         mesh.name = $"HairStrip_{strip.index}";
//         mesh.vertices = newVerts;
//         mesh.uv = newUVs;
//         mesh.normals = newNormals;
//         mesh.colors = newColors;
//
//         if (newTriangles.Count >= 3)
//         {
//             mesh.triangles = newTriangles.ToArray();
//         }
//
//         mesh.RecalculateBounds();
//
//         return mesh;
//     }
//
//     #region Helper Methods
//     
//     private Mesh GetMesh()
//     {
//         if (targetObject == null) return null;
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         return mf?.sharedMesh ?? smr?.sharedMesh;
//     }
//     
//     private void ApplyMesh(Mesh mesh)
//     {
//         var mf = targetObject.GetComponent<MeshFilter>();
//         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
//         if (mf != null) mf.sharedMesh = mesh;
//         else if (smr != null) smr.sharedMesh = mesh;
//     }
//     
//     private Dictionary<int, HashSet<int>> BuildAdjacencyList(int[] triangles, int vertexCount)
//     {
//         var adj = new Dictionary<int, HashSet<int>>();
//         for (int i = 0; i < vertexCount; i++) adj[i] = new HashSet<int>();
//         
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
//             adj[v0].Add(v1); adj[v0].Add(v2);
//             adj[v1].Add(v0); adj[v1].Add(v2);
//             adj[v2].Add(v0); adj[v2].Add(v1);
//         }
//         return adj;
//     }
//     
//     private Dictionary<int, List<int>> BuildVertexToTrianglesMap(int[] triangles)
//     {
//         var map = new Dictionary<int, List<int>>();
//         for (int i = 0; i < triangles.Length; i += 3)
//         {
//             int triIdx = i / 3;
//             for (int j = 0; j < 3; j++)
//             {
//                 int v = triangles[i + j];
//                 if (!map.ContainsKey(v)) map[v] = new List<int>();
//                 map[v].Add(triIdx);
//             }
//         }
//         return map;
//     }
//     
//     private void AddEdgeTriangle(Dictionary<Edge, List<int>> dict, int v0, int v1, int triIndex)
//     {
//         Edge edge = new Edge(v0, v1);
//         if (!dict.ContainsKey(edge)) dict[edge] = new List<int>();
//         dict[edge].Add(triIndex);
//     }
//     
//     public struct Edge : System.IEquatable<Edge>
//     {
//         public int v0, v1;
//         public Edge(int a, int b) { v0 = Mathf.Min(a, b); v1 = Mathf.Max(a, b); }
//         public bool Equals(Edge other) => v0 == other.v0 && v1 == other.v1;
//         public override int GetHashCode() => v0 ^ (v1 << 16);
//     }
//     
//     public class UnionFind
//     {
//         private int[] parent, rank;
//         public UnionFind(int n)
//         {
//             parent = new int[n]; rank = new int[n];
//             for (int i = 0; i < n; i++) parent[i] = i;
//         }
//         public int Find(int x) { if (parent[x] != x) parent[x] = Find(parent[x]); return parent[x]; }
//         public void Union(int x, int y)
//         {
//             int px = Find(x), py = Find(y);
//             if (px == py) return;
//             if (rank[px] < rank[py]) parent[px] = py;
//             else if (rank[px] > rank[py]) parent[py] = px;
//             else { parent[py] = px; rank[px]++; }
//         }
//     }
//     
//     #endregion
// }
//--------------------------以下增加了世界坐标Y来修正(Root节点的maxY和minY的区间) finalB*0.5f+0.5f; 适配负偏移----------------------
 // using UnityEngine;
 // using UnityEditor;
 // using System.Collections.Generic;
 // using System.Linq;
 //
 // public class HairAnalyzerVisualizerV2 : EditorWindow
 // {
 //     private GameObject targetObject;
 //     private Mesh analyzedMesh;
 //     
 //     // 分析结果
 //     private List<HairStrip> hairStrips = new List<HairStrip>();
 //     private int currentStripIndex = 0;
 //     
 //     // 全局UV统计
 //     private float globalMinV = 0f;
 //     private float globalMaxV = 1f;
 //     private float globalVRange = 1f;
 //     
 //     // 【新增】全局世界Y统计
 //     private float globalMinWorldY = 0f;
 //     private float globalMaxWorldY = 1f;
 //     private float globalWorldYRange = 1f;
 //     
 //     // 可视化设置
 //     private bool showAllStrips = true;
 //     private bool showVertexLabels = false;
 //     private bool showUVInfo = true;
 //     private bool showRootTipMarkers = true;
 //     private float vertexSphereSize = 0.002f;
 //     
 //     // 分析参数
 //     private float rootThreshold = 0.05f;
 //     private float uvContinuityThreshold = 0.3f;
 //     private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
 //     
 //     // UV差值计算模式
 //     private UVDifferenceMode uvDifferenceMode = UVDifferenceMode.PerStrip;
 //     
 //     // 【新增】世界坐标修正设置
 //     private bool enableWorldYCorrection = false;
 //     private WorldYCorrectionMode worldYCorrectionMode = WorldYCorrectionMode.AddToUV;
 //     private float worldYCorrectionWeight = 1.0f; // 修正权重
 //     private bool useRootWorldY = true; // true=使用根部Y, false=使用平均Y
 //     
 //     // 日志设置
 //     private bool enableDetailedLog = false;
 //     private bool logToFile = false;
 //     private int maxLogEntries = 100;
 //     
 //     // 排除统计
 //     private Dictionary<string, int> exclusionStats = new Dictionary<string, int>();
 //     private List<string> detailedLogs = new List<string>();
 //     
 //     private Vector2 scrollPos;
 //     private bool analysisComplete = false;
 //     
 //     public enum AnalysisMethod
 //     {
 //         UVBased,
 //         TriangleStrip,
 //         ConnectedComponent
 //     }
 //     
 //     public enum UVDifferenceMode
 //     {
 //         [InspectorName("单片独立计算")]
 //         PerStrip,
 //         [InspectorName("全局V值计算")]
 //         GlobalV,
 //         [InspectorName("全局范围归一化")]
 //         GlobalRange
 //     }
 //     
 //     /// <summary>
 //     /// 【新增】世界Y坐标修正模式
 //     /// </summary>
 //     public enum WorldYCorrectionMode
 //     {
 //         [InspectorName("叠加到UV差值")]
 //         AddToUV,              // 将Y偏移值加到UV差值上
 //         [InspectorName("乘以UV差值")]
 //         MultiplyUV,           // 将Y偏移值乘以UV差值
 //         [InspectorName("作为起始偏移")]
 //         AsStartOffset,        // 作为流光起始时间偏移
 //         [InspectorName("混合模式")]
 //         Blend                 // 按权重混合UV差值和Y偏移
 //     }
 //
 //     /// <summary>
 //     /// 毛发条带数据
 //     /// </summary>
 //     public class HairStrip
 //     {
 //         public int index;
 //         public List<int> vertexIndices = new List<int>();
 //         public List<int> triangleIndices = new List<int>();
 //         public Color debugColor;
 //         
 //         // UV统计
 //         public float minV;
 //         public float maxV;
 //         
 //         public Vector3 rootPosition;
 //         public Vector3 tipPosition;
 //         
 //         // 【新增】世界Y统计
 //         public float rootWorldY;      // 根部世界Y坐标
 //         public float tipWorldY;       // 尖端世界Y坐标
 //         public float avgWorldY;       // 平均世界Y坐标
 //         public float minWorldY;       // 最小世界Y
 //         public float maxWorldY;       // 最大世界Y
 //         public float worldYOffset;    // 计算后的Y偏移值(0-1)
 //         
 //         public int vertexCount => vertexIndices.Count;
 //         public int triangleCount => triangleIndices.Count / 3;
 //         public float vRange => maxV - minV;
 //     }
 //
 //     [MenuItem("Tools/Hair/Hair Analyzer Visualizer")]
 //     public static void ShowWindow()
 //     {
 //         var window = GetWindow<HairAnalyzerVisualizerV2>("毛发分析可视化");
 //         window.minSize = new Vector2(420, 700);
 //     }
 //
 //     private void OnEnable()
 //     {
 //         SceneView.duringSceneGui += OnSceneGUI;
 //     }
 //
 //     private void OnDisable()
 //     {
 //         SceneView.duringSceneGui -= OnSceneGUI;
 //     }
 //
 //     private void OnGUI()
 //     {
 //         scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
 //         
 //         DrawHeader();
 //          DrawInputSection();
 //          DrawAnalysisSettings();
 //          DrawWorldYCorrectionSettings(); // 【新增】世界Y修正设置
 //          DrawLogSettings();
 //          DrawAnalysisButtons();
 //         
 //          if (analysisComplete)
 //          {
 //              DrawResultsSection();
 //              DrawWorldYStatsSection(); // 【新增】世界Y统计显示
 //              DrawExclusionStats();
 //              DrawStripNavigator();
 //              DrawVisualizationSettings();
 //              DrawExportSection();
 //          }
 //         // 添加这行测试 - 如果能看到说明滚动到底了
 //         EditorGUILayout.HelpBox("=== 这是窗口底部 ===", MessageType.Info);
 //         
 //         EditorGUILayout.EndScrollView();
 //     }
 //
 //     private void DrawHeader()
 //     {
 //         EditorGUILayout.Space(10);
 //         
 //         GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
 //         {
 //             fontSize = 16,
 //             alignment = TextAnchor.MiddleCenter
 //         };
 //         GUILayout.Label("🔍 毛发结构分析与可视化", titleStyle);
 //         
 //         EditorGUILayout.Space(5);
 //         
 //         EditorGUILayout.HelpBox(
 //             "UV规则：\n" +
 //             "• ROOT（根部）= V值最大 → 显示为绿色\n" +
 //             "• TIP（尖端）= V值最小 → 显示为红色\n" +
 //             "• 差值结果：根部=1，尖端=0", 
 //             MessageType.Info);
 //         
 //         EditorGUILayout.Space(10);
 //     }
 //
 //     private void DrawInputSection()
 //     {
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("📥 输入", EditorStyles.boldLabel);
 //         
 //         EditorGUI.BeginChangeCheck();
 //         targetObject = (GameObject)EditorGUILayout.ObjectField(
 //             "目标物体", targetObject, typeof(GameObject), true);
 //         if (EditorGUI.EndChangeCheck())
 //         {
 //             analysisComplete = false;
 //             hairStrips.Clear();
 //         }
 //         
 //         if (targetObject != null)
 //         {
 //             Mesh mesh = GetMesh();
 //             if (mesh != null)
 //             {
 //                 EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
 //                 EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
 //                 
 //                 if (mesh.uv != null && mesh.uv.Length > 0)
 //                 {
 //                     float minV = mesh.uv.Min(uv => uv.y);
 //                     float maxV = mesh.uv.Max(uv => uv.y);
 //                     EditorGUILayout.LabelField("UV V值范围", $"{minV:F3} ~ {maxV:F3}");
 //                 }
 //                 else
 //                 {
 //                     EditorGUILayout.HelpBox("警告：Mesh没有UV数据！", MessageType.Warning);
 //                 }
 //             }
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawAnalysisSettings()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("⚙️ 分析设置", EditorStyles.boldLabel);
 //         
 //         analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
 //         
 //         string methodDesc = "";
 //         switch (analysisMethod)
 //         {
 //             case AnalysisMethod.UVBased:
 //                 methodDesc = "从V值最大的点(根部)出发，沿V递减方向追踪";
 //                 break;
 //             case AnalysisMethod.TriangleStrip:
 //                 methodDesc = "通过共享边的三角形分组";
 //                 break;
 //             case AnalysisMethod.ConnectedComponent:
 //                 methodDesc = "完全独立的三角形组为一片";
 //                 break;
 //         }
 //         EditorGUILayout.HelpBox(methodDesc, MessageType.None);
 //         
 //         rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
 //         uvContinuityThreshold = EditorGUILayout.Slider("UV连续性阈值", uvContinuityThreshold, 0.1f, 0.5f);
 //         
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.LabelField("UV差值计算", EditorStyles.boldLabel);
 //         
 //         uvDifferenceMode = (UVDifferenceMode)EditorGUILayout.EnumPopup("计算模式", uvDifferenceMode);
 //         
 //         string modeDesc = "";
 //         switch (uvDifferenceMode)
 //         {
 //             case UVDifferenceMode.PerStrip:
 //                 modeDesc = "每片毛发独立归一化\ndiff = (V - 片内minV) / 片内vRange\n根部=1, 尖端=0";
 //                 break;
 //             case UVDifferenceMode.GlobalV:
 //                 modeDesc = "统一根部起点（全局maxV）\ndiff = (全局maxV - 片内maxV) \n根部=1, 尖端=0";
 //                 break;
 //             case UVDifferenceMode.GlobalRange:
 //                 modeDesc = "使用全局V范围归一化\ndiff = (V - 全局minV) / 全局vRange\n根部=1, 尖端=0";
 //                 break;
 //         }
 //         EditorGUILayout.HelpBox(modeDesc, MessageType.None);
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     /// <summary>
 //     /// 【新增】世界Y坐标修正设置UI
 //     /// </summary>
 //     private void DrawWorldYCorrectionSettings()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //
 //         EditorGUILayout.BeginHorizontal();
 //         GUILayout.Label("🌍 世界坐标Y修正", EditorStyles.boldLabel);
 //         enableWorldYCorrection = EditorGUILayout.Toggle(enableWorldYCorrection, GUILayout.Width(20));
 //         EditorGUILayout.EndHorizontal();
 //
 //         if (enableWorldYCorrection)
 //         {
 //             EditorGUI.indentLevel++;
 //
 //             worldYCorrectionMode = (WorldYCorrectionMode)EditorGUILayout.EnumPopup("修正模式", worldYCorrectionMode);
 //
 //             // 模式说明
 //             string correctionDesc = "";
 //             switch (worldYCorrectionMode)
 //             {
 //                 case WorldYCorrectionMode.AddToUV:
 //                     correctionDesc = "最终值 = UV差值 + Y偏移 × 权重\n适合：让低处的毛发流光延迟开始";
 //                     break;
 //                 case WorldYCorrectionMode.MultiplyUV:
 //                     correctionDesc = "最终值 = UV差值 × (1 + Y偏移 × 权重)\n适合：低处毛发流光速度调整";
 //                     break;
 //                 case WorldYCorrectionMode.AsStartOffset:
 //                     correctionDesc = "最终值 = UV差值 + Y偏移(仅根部)\n适合：不同高度毛发分批启动";
 //                     break;
 //                 case WorldYCorrectionMode.Blend:
 //                     correctionDesc = "最终值 = lerp(UV差值, Y偏移, 权重)\n适合：部分依赖位置的流光";
 //                     break;
 //             }
 //
 //             EditorGUILayout.HelpBox(correctionDesc, MessageType.None);
 //
 //             worldYCorrectionWeight = EditorGUILayout.Slider("修正权重", worldYCorrectionWeight, 0f, 2f);
 //
 //             useRootWorldY = EditorGUILayout.Toggle("使用根部Y坐标", useRootWorldY);
 //             if (!useRootWorldY)
 //             {
 //                 EditorGUILayout.LabelField("  (将使用Strip平均Y坐标)", EditorStyles.miniLabel);
 //             }
 //
 //             EditorGUILayout.Space(3);
 //             EditorGUILayout.HelpBox(
 //                 "Y偏移计算公式（从高到低流动）：\n" +
 //                 "yOffset = (globalMaxY - stripY) / globalYRange\n" +
 //                 "• 最高处Strip: yOffset = 0（先开始）\n" +
 //                 "• 最低处Strip: yOffset = 1（后开始）",
 //                 MessageType.Info);
 //
 //             EditorGUI.indentLevel--;
 //         }
 //
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawWorldYStatsSection()
 //     {
 //         if (!enableWorldYCorrection) return;
 //
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("🌍 世界Y坐标统计", EditorStyles.boldLabel);
 //
 //         EditorGUILayout.BeginHorizontal();
 //         EditorGUILayout.LabelField($"全局 Min Y: {globalMinWorldY:F4}", GUILayout.Width(180));
 //         EditorGUILayout.LabelField($"全局 Max Y: {globalMaxWorldY:F4}");
 //         EditorGUILayout.EndHorizontal();
 //         EditorGUILayout.LabelField($"全局 Y Range: {globalWorldYRange:F4}");
 //
 //         if (hairStrips.Count > 0)
 //         {
 //             EditorGUILayout.Space(3);
 //        
 //             // 【新增】显示根节点UV范围
 //             float rootUVMin = hairStrips.Min(s => s.maxV);
 //             float rootUVMax = hairStrips.Max(s => s.maxV);
 //             float rootUVRange = rootUVMax - rootUVMin;
 //             EditorGUILayout.LabelField($"根节点UV范围: {rootUVMin:F4} ~ {rootUVMax:F4} (Range={rootUVRange:F4})");
 //
 //             var yOffsets = hairStrips.Select(s => s.worldYOffset).ToList();
 //             EditorGUILayout.LabelField($"Strip Y偏移范围: {yOffsets.Min():F4} ~ {yOffsets.Max():F4}");
 //
 //             // 显示Y偏移分布
 //             float offsetRange = yOffsets.Max() - yOffsets.Min();
 //             float lowThreshold = offsetRange * 0.33f;
 //             float highThreshold = offsetRange * 0.66f;
 //        
 //             var earlyStart = hairStrips.Count(s => s.worldYOffset < lowThreshold);
 //             var midStart = hairStrips.Count(s => s.worldYOffset >= lowThreshold && s.worldYOffset < highThreshold);
 //             var lateStart = hairStrips.Count(s => s.worldYOffset >= highThreshold);
 //
 //             EditorGUILayout.LabelField($"启动顺序分布: 早({earlyStart}高处) 中({midStart}) 晚({lateStart}低处)");
 //         }
 //
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawLogSettings()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("📋 日志设置", EditorStyles.boldLabel);
 //         
 //         enableDetailedLog = EditorGUILayout.Toggle("启用详细日志", enableDetailedLog);
 //         
 //         if (enableDetailedLog)
 //         {
 //             EditorGUI.indentLevel++;
 //             maxLogEntries = EditorGUILayout.IntSlider("控制台最大条数", maxLogEntries, 10, 500);
 //             logToFile = EditorGUILayout.Toggle("同时输出到文件", logToFile);
 //             EditorGUI.indentLevel--;
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawExclusionStats()
 //     {
 //         if (exclusionStats.Count == 0) return;
 //         
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("📊 顶点排除统计", EditorStyles.boldLabel);
 //         
 //         foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
 //         {
 //             EditorGUILayout.BeginHorizontal();
 //             EditorGUILayout.LabelField(kvp.Key, GUILayout.Width(250));
 //             EditorGUILayout.LabelField(kvp.Value.ToString(), EditorStyles.boldLabel);
 //             EditorGUILayout.EndHorizontal();
 //         }
 //         
 //         EditorGUILayout.Space(3);
 //         if (GUILayout.Button("导出详细日志"))
 //         {
 //             ExportDetailedLog();
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawAnalysisButtons()
 //     {
 //         EditorGUILayout.Space(10);
 //         
 //         GUI.enabled = targetObject != null && GetMesh() != null;
 //         
 //         GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
 //         if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
 //         {
 //             PerformAnalysis();
 //         }
 //         GUI.backgroundColor = Color.white;
 //         
 //         GUI.enabled = true;
 //     }
 //
 //     private void DrawResultsSection()
 //     {
 //         EditorGUILayout.Space(10);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
 //         
 //         EditorGUILayout.LabelField("识别到的毛发片", hairStrips.Count.ToString());
 //         
 //         EditorGUILayout.Space(3);
 //         EditorGUILayout.LabelField("全局UV统计", EditorStyles.boldLabel);
 //         EditorGUILayout.BeginHorizontal();
 //         EditorGUILayout.LabelField($"全局 Min V: {globalMinV:F4}", GUILayout.Width(150));
 //         EditorGUILayout.LabelField($"全局 Max V: {globalMaxV:F4}");
 //         EditorGUILayout.EndHorizontal();
 //         EditorGUILayout.LabelField($"全局 V Range: {globalVRange:F4}");
 //         
 //         if (hairStrips.Count > 0)
 //         {
 //             EditorGUILayout.Space(3);
 //             var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
 //             var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
 //             var vRanges = hairStrips.Select(s => s.vRange).ToList();
 //             
 //             EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} ~ {vertexCounts.Max()} (平均:{vertexCounts.Average():F1})");
 //             EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} ~ {triCounts.Max()}");
 //             EditorGUILayout.LabelField("单片V值跨度范围", $"{vRanges.Min():F3} ~ {vRanges.Max():F3}");
 //             
 //             int tooSmall = hairStrips.Count(s => s.vertexCount < 3);
 //             int tooLarge = hairStrips.Count(s => s.vertexCount > 50);
 //             int noVRange = hairStrips.Count(s => s.vRange < 0.01f);
 //             
 //             if (tooSmall > 0 || tooLarge > 0 || noVRange > 0)
 //             {
 //                 string warning = "检测到异常：\n";
 //                 if (tooSmall > 0) warning += $"• {tooSmall} 片顶点数过少(<3)\n";
 //                 if (tooLarge > 0) warning += $"• {tooLarge} 片顶点数过多(>50)\n";
 //                 if (noVRange > 0) warning += $"• {noVRange} 片V值跨度过小(<0.01)";
 //                 EditorGUILayout.HelpBox(warning, MessageType.Warning);
 //             }
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawStripNavigator()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
 //         
 //         if (hairStrips.Count > 0)
 //         {
 //             EditorGUILayout.BeginHorizontal();
 //             
 //             if (GUILayout.Button("◀", GUILayout.Width(40)))
 //             {
 //                 currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
 //                 FocusOnStrip(currentStripIndex);
 //             }
 //             
 //             currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
 //             
 //             if (GUILayout.Button("▶", GUILayout.Width(40)))
 //             {
 //                 currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
 //                 FocusOnStrip(currentStripIndex);
 //             }
 //             
 //             EditorGUILayout.EndHorizontal();
 //             
 //             if (currentStripIndex < hairStrips.Count)
 //             {
 //                 var strip = hairStrips[currentStripIndex];
 //                 
 //                 EditorGUILayout.Space(5);
 //                 EditorGUILayout.BeginVertical("helpbox");
 //                 
 //                 EditorGUILayout.LabelField($"毛发片 #{strip.index}", EditorStyles.boldLabel);
 //                 
 //                 EditorGUILayout.BeginHorizontal();
 //                 EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString(), GUILayout.Width(150));
 //                 EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
 //                 EditorGUILayout.EndHorizontal();
 //                 
 //                 EditorGUILayout.BeginHorizontal();
 //                 EditorGUILayout.LabelField("根部V值(MAX)", $"{strip.maxV:F4}", GUILayout.Width(150));
 //                 EditorGUILayout.LabelField("尖端V值(MIN)", $"{strip.minV:F4}");
 //                 EditorGUILayout.EndHorizontal();
 //                 
 //                 EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F4}");
 //                 
 //                 // 【新增】显示世界Y信息
 //                 if (enableWorldYCorrection)
 //                 {
 //                     EditorGUILayout.Space(3);
 //                     EditorGUILayout.LabelField("世界Y坐标", EditorStyles.miniBoldLabel);
 //                     EditorGUILayout.BeginHorizontal();
 //                     EditorGUILayout.LabelField($"根部Y: {strip.rootWorldY:F4}", GUILayout.Width(150));
 //                     EditorGUILayout.LabelField($"尖端Y: {strip.tipWorldY:F4}");
 //                     EditorGUILayout.EndHorizontal();
 //                     EditorGUILayout.LabelField($"Y偏移值: {strip.worldYOffset:F4}");
 //                 }
 //                 
 //                 // 差值预览
 //                 float rootDiff = CalculateUVDifference(strip.maxV, strip);
 //                 float tipDiff = CalculateUVDifference(strip.minV, strip);
 //                 
 //                 // 【新增】带Y修正的最终值预览
 //                 if (enableWorldYCorrection)
 //                 {
 //                     float rootFinal = ApplyWorldYCorrection(rootDiff, strip);
 //                     float tipFinal = ApplyWorldYCorrection(tipDiff, strip);
 //                     EditorGUILayout.LabelField($"UV差值: 根部={rootDiff:F3}, 尖端={tipDiff:F3}");
 //                     EditorGUILayout.LabelField($"最终值(+Y修正): 根部={rootFinal:F3}, 尖端={tipFinal:F3}");
 //                 }
 //                 else
 //                 {
 //                     EditorGUILayout.LabelField($"差值预览: 根部={rootDiff:F3}, 尖端={tipDiff:F3}");
 //                 }
 //                 
 //                 string vertPreview = string.Join(", ", strip.vertexIndices.Take(15));
 //                 if (strip.vertexIndices.Count > 15) vertPreview += "...";
 //                 EditorGUILayout.LabelField("顶点:", vertPreview, EditorStyles.miniLabel);
 //                 
 //                 EditorGUILayout.EndVertical();
 //                 
 //                 EditorGUILayout.BeginHorizontal();
 //                 if (GUILayout.Button("聚焦此片"))
 //                 {
 //                     FocusOnStrip(currentStripIndex);
 //                 }
 //                 if (GUILayout.Button("导出此片"))
 //                 {
 //                     ExportSingleStrip(strip);
 //                 }
 //                 EditorGUILayout.EndHorizontal();
 //             }
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawVisualizationSettings()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
 //         
 //         showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
 //         showVertexLabels = EditorGUILayout.Toggle("显示顶点索引", showVertexLabels);
 //         showUVInfo = EditorGUILayout.Toggle("显示UV V值", showUVInfo);
 //         showRootTipMarkers = EditorGUILayout.Toggle("显示根部/尖端标记", showRootTipMarkers);
 //         vertexSphereSize = EditorGUILayout.Slider("顶点大小", vertexSphereSize, 0.0005f, 0.02f);
 //         
 //         EditorGUILayout.BeginHorizontal();
 //         if (GUILayout.Button("刷新视图"))
 //         {
 //             SceneView.RepaintAll();
 //         }
 //         if (GUILayout.Button("重置相机"))
 //         {
 //             if (targetObject != null)
 //             {
 //                 SceneView.lastActiveSceneView?.LookAt(targetObject.transform.position);
 //             }
 //         }
 //         EditorGUILayout.EndHorizontal();
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     private void DrawExportSection()
 //     {
 //         EditorGUILayout.Space(5);
 //         EditorGUILayout.BeginVertical("box");
 //         GUILayout.Label("📤 导出", EditorStyles.boldLabel);
 //         
 //         EditorGUILayout.LabelField($"UV差值模式: {uvDifferenceMode}", EditorStyles.miniLabel);
 //         if (enableWorldYCorrection)
 //         {
 //             EditorGUILayout.LabelField($"世界Y修正: {worldYCorrectionMode} (权重:{worldYCorrectionWeight:F2})", EditorStyles.miniLabel);
 //         }
 //         
 //         if (GUILayout.Button("生成带UV差值的Mesh"))
 //         {
 //             GenerateMeshWithUVDifference();
 //         }
 //         
 //         if (GUILayout.Button("导出所有毛发片"))
 //         {
 //             ExportAllStrips();
 //         }
 //         
 //         if (GUILayout.Button("导出分析报告"))
 //         {
 //             ExportAnalysisReport();
 //         }
 //         
 //         EditorGUILayout.EndVertical();
 //     }
 //
 //     /// <summary>
 //     /// 根据当前模式计算UV差值（不含Y修正）
 //     /// </summary>
 //     private float CalculateUVDifference(float vValue, HairStrip strip)
 //     {
 //         switch (uvDifferenceMode)
 //         {
 //             case UVDifferenceMode.PerStrip:
 //                 return strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0f;
 //                 
 //             case UVDifferenceMode.GlobalV:
 //                 return globalMaxV - strip.maxV;
 //                 
 //             case UVDifferenceMode.GlobalRange:
 //                 return globalVRange > 0.001f ? (vValue - globalMinV) / globalVRange : 0f;
 //                 
 //             default:
 //                 return 0f;
 //         }
 //     }
 //
 //     /// <summary>
 //     /// 【新增】应用世界Y坐标修正
 //     /// </summary>
 //     private float ApplyWorldYCorrection(float uvDiff, HairStrip strip)
 //     {
 //         if (!enableWorldYCorrection)
 //             return uvDiff;
 //         
 //         float yOffset = strip.worldYOffset;
 //         float weight = worldYCorrectionWeight;
 //         
 //         switch (worldYCorrectionMode)
 //         {
 //             case WorldYCorrectionMode.AddToUV:
 //                 // 直接叠加：让高处的毛发B值变小，流光更快开始
 //                 return uvDiff - yOffset * weight;
 //                 
 //             case WorldYCorrectionMode.MultiplyUV:
 //                 // 乘法调整：高处毛发的差值被放大
 //                 return uvDiff * (1f - yOffset * weight);
 //                 
 //             case WorldYCorrectionMode.AsStartOffset:
 //                 // 作为起始偏移：只在根部(uvDiff接近1)时添加偏移
 //                 float rootInfluence = Mathf.Pow(uvDiff, 2f); // 根部影响更大
 //                 return uvDiff - yOffset * weight * rootInfluence;
 //                 
 //             case WorldYCorrectionMode.Blend:
 //                 // 混合模式：按权重在UV差值和Y偏移之间插值
 //                 return Mathf.Lerp(uvDiff, -yOffset, weight);
 //                 
 //             default:
 //                 return uvDiff;
 //         }
 //     }
 //
 //     /// <summary>
 //     /// 【新增】计算单个顶点的最终B值
 //     /// </summary>
 //     private float CalculateFinalBValue(float vValue, HairStrip strip)
 //     {
 //         float uvDiff = CalculateUVDifference(vValue, strip);
 //         return ApplyWorldYCorrection(uvDiff, strip);
 //     }
 //
 //     private void AddLog(string message)
 //     {
 //         if (!enableDetailedLog) return;
 //         detailedLogs.Add($"[{System.DateTime.Now:HH:mm:ss.fff}] {message}");
 //     }
 //
 //     private void AddExclusionStat(string reason)
 //     {
 //         if (!exclusionStats.ContainsKey(reason))
 //             exclusionStats[reason] = 0;
 //         exclusionStats[reason]++;
 //     }
 //
 //     /// <summary>
 //     /// 执行分析
 //     /// </summary>
 //     private void PerformAnalysis()
 //     {
 //         analyzedMesh = GetMesh();
 //         if (analyzedMesh == null) return;
 //         
 //         hairStrips.Clear();
 //         exclusionStats.Clear();
 //         detailedLogs.Clear();
 //         
 //         AddLog("========== 开始毛发分析 ==========");
 //         AddLog($"Mesh: {analyzedMesh.name}, 顶点数: {analyzedMesh.vertexCount}, 三角形数: {analyzedMesh.triangles.Length / 3}");
 //         
 //         // 计算全局UV统计
 //         CalculateGlobalUVStats();
 //         AddLog($"全局UV统计: MinV={globalMinV:F4}, MaxV={globalMaxV:F4}, Range={globalVRange:F4}");
 //         
 //         switch (analysisMethod)
 //         {
 //             case AnalysisMethod.UVBased:
 //                 AnalyzeByUV();
 //                 break;
 //             case AnalysisMethod.TriangleStrip:
 //             case AnalysisMethod.ConnectedComponent:
 //                 AnalyzeByConnectedComponent();
 //                 break;
 //         }
 //         
 //         // 【新增】计算世界Y统计和偏移
 //         if (enableWorldYCorrection)
 //         {
 //             CalculateWorldYStats();
 //         }
 //         
 //         // 分配随机颜色
 //         System.Random rand = new System.Random(42);
 //         foreach (var strip in hairStrips)
 //         {
 //             strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
 //         }
 //         
 //         analysisComplete = true;
 //         currentStripIndex = 0;
 //         
 //         // 输出日志
 //         Debug.Log($"✓ 分析完成！识别到 {hairStrips.Count} 个毛发片");
 //         Debug.Log($"  全局UV范围: V = {globalMinV:F4} ~ {globalMaxV:F4}");
 //         
 //         if (enableWorldYCorrection)
 //         {
 //             Debug.Log($"  全局世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4}");
 //         }
 //         
 //         if (enableDetailedLog)
 //         {
 //             Debug.Log("---------- 排除统计 ----------");
 //             foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
 //             {
 //                 Debug.Log($"  {kvp.Key}: {kvp.Value}");
 //             }
 //             
 //             int logCount = Mathf.Min(detailedLogs.Count, maxLogEntries);
 //             Debug.Log($"---------- 详细日志 (显示前{logCount}条) ----------");
 //             for (int i = 0; i < logCount; i++)
 //             {
 //                 Debug.Log(detailedLogs[i]);
 //             }
 //             
 //             if (logToFile)
 //             {
 //                 ExportDetailedLog();
 //             }
 //         }
 //         
 //         SceneView.RepaintAll();
 //     }
 //
 //     /// <summary>
 //     /// 计算全局UV统计
 //     /// </summary>
 //     private void CalculateGlobalUVStats()
 //     {
 //         Vector2[] uvs = analyzedMesh.uv;
 //         
 //         if (uvs == null || uvs.Length == 0)
 //         {
 //             globalMinV = 0f;
 //             globalMaxV = 1f;
 //             globalVRange = 1f;
 //             return;
 //         }
 //         
 //         globalMinV = float.MaxValue;
 //         globalMaxV = float.MinValue;
 //         
 //         foreach (var uv in uvs)
 //         {
 //             if (uv.y < globalMinV) globalMinV = uv.y;
 //             if (uv.y > globalMaxV) globalMaxV = uv.y;
 //         }
 //         
 //         globalVRange = globalMaxV - globalMinV;
 //         if (globalVRange < 0.001f) globalVRange = 1f;
 //     }
 //
 //     /// <summary>
 //     /// 【修正】计算全局世界Y统计和每个Strip的Y偏移
 //     /// Y偏移范围映射到根节点UV范围（所有Strip的maxV的min~max）
 //     /// </summary>
 //     private void CalculateWorldYStats()
 //     {
 //         if (hairStrips.Count == 0) return;
 //
 //         Vector3[] vertices = analyzedMesh.vertices;
 //         Vector2[] uvs = analyzedMesh.uv;
 //         Transform transform = targetObject.transform;
 //
 //         AddLog("");
 //         AddLog("========== 计算世界Y坐标统计 ==========");
 //         AddLog("规则：高处yOffset=小值（先开始），低处yOffset=大值（后开始）");
 //
 //         // 第一遍：计算每个Strip的世界Y信息
 //         foreach (var strip in hairStrips)
 //         {
 //             float sumY = 0f;
 //             float minY = float.MaxValue;
 //             float maxY = float.MinValue;
 //
 //             // 找到根部和尖端顶点
 //             int rootVertIdx = -1;
 //             int tipVertIdx = -1;
 //             float maxV = float.MinValue;
 //             float minV = float.MaxValue;
 //
 //             foreach (int vertIdx in strip.vertexIndices)
 //             {
 //                 Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
 //                 float y = worldPos.y;
 //
 //                 sumY += y;
 //                 if (y < minY) minY = y;
 //                 if (y > maxY) maxY = y;
 //
 //                 float v = uvs[vertIdx].y;
 //                 if (v > maxV)
 //                 {
 //                     maxV = v;
 //                     rootVertIdx = vertIdx;
 //                 }
 //
 //                 if (v < minV)
 //                 {
 //                     minV = v;
 //                     tipVertIdx = vertIdx;
 //                 }
 //             }
 //
 //             strip.avgWorldY = sumY / strip.vertexIndices.Count;
 //             strip.minWorldY = minY;
 //             strip.maxWorldY = maxY;
 //
 //             if (rootVertIdx >= 0)
 //             {
 //                 strip.rootWorldY = transform.TransformPoint(vertices[rootVertIdx]).y;
 //             }
 //
 //             if (tipVertIdx >= 0)
 //             {
 //                 strip.tipWorldY = transform.TransformPoint(vertices[tipVertIdx]).y;
 //             }
 //         }
 //
 //         // 计算全局Y范围（基于根部Y或平均Y）
 //         if (useRootWorldY)
 //         {
 //             globalMinWorldY = hairStrips.Min(s => s.rootWorldY);
 //             globalMaxWorldY = hairStrips.Max(s => s.rootWorldY);
 //         }
 //         else
 //         {
 //             globalMinWorldY = hairStrips.Min(s => s.avgWorldY);
 //             globalMaxWorldY = hairStrips.Max(s => s.avgWorldY);
 //         }
 //
 //         globalWorldYRange = globalMaxWorldY - globalMinWorldY;
 //         if (globalWorldYRange < 0.001f) globalWorldYRange = 1f;
 //
 //         // 【新增】计算根节点UV范围（所有Strip的maxV的最小值和最大值）
 //         float rootUVMin = hairStrips.Min(s => s.maxV); // 所有根部V值中的最小值
 //         float rootUVMax = hairStrips.Max(s => s.maxV); // 所有根部V值中的最大值
 //         float rootUVRange = rootUVMax - rootUVMin;
 //
 //         AddLog($"全局世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4} (Range={globalWorldYRange:F4})");
 //         AddLog($"根节点UV范围: {rootUVMin:F4} ~ {rootUVMax:F4} (Range={rootUVRange:F4})");
 //         AddLog($"使用: {(useRootWorldY ? "根部Y" : "平均Y")}");
 //
 //         // 第二遍：计算每个Strip的Y偏移值
 //         // 【修正】映射到根节点UV范围，而不是0-1
 //         foreach (var strip in hairStrips)
 //         {
 //             float referenceY = useRootWorldY ? strip.rootWorldY : strip.avgWorldY;
 //
 //             // 计算Y的归一化值 (0-1范围)
 //             // 高处=0，低处=1（从高到低流动）
 //             float yNormalized = (globalMaxWorldY - referenceY) / globalWorldYRange;
 //             yNormalized = Mathf.Clamp01(yNormalized);
 //
 //             // 【关键修正】将0-1范围映射到根节点UV范围
 //             // 这样Y偏移的量级与UV差值匹配
 //             strip.worldYOffset = Mathf.Lerp(rootUVMin, rootUVMax, yNormalized) - rootUVMin;
 //
 //             // 或者更简单的写法：直接映射到rootUVRange
 //             // strip.worldYOffset = yNormalized * rootUVRange;
 //         }
 //
 //         // 计算实际的Y偏移范围用于验证
 //         float actualMinOffset = hairStrips.Min(s => s.worldYOffset);
 //         float actualMaxOffset = hairStrips.Max(s => s.worldYOffset);
 //
 //         AddLog($"Strip Y偏移范围: {actualMinOffset:F4} ~ {actualMaxOffset:F4}");
 //         AddLog($"目标范围(rootUVRange): 0 ~ {rootUVRange:F4}");
 //         AddLog("验证：最高处Strip的yOffset应接近0，最低处应接近rootUVRange");
 //
 //         // 输出部分Strip的Y信息用于验证
 //         var sortedByY = hairStrips.OrderByDescending(s => useRootWorldY ? s.rootWorldY : s.avgWorldY).ToList();
 //         int logCount = Mathf.Min(sortedByY.Count, 5);
 //
 //         AddLog($"最高的{logCount}个Strip:");
 //         for (int i = 0; i < logCount; i++)
 //         {
 //             var strip = sortedByY[i];
 //             float refY = useRootWorldY ? strip.rootWorldY : strip.avgWorldY;
 //             AddLog($"  Strip #{strip.index}: Y={refY:F4}, rootV={strip.maxV:F4}, yOffset={strip.worldYOffset:F4}");
 //         }
 //
 //         AddLog($"最低的{logCount}个Strip:");
 //         for (int i = 0; i < logCount; i++)
 //         {
 //             var strip = sortedByY[sortedByY.Count - 1 - i];
 //             float refY = useRootWorldY ? strip.rootWorldY : strip.avgWorldY;
 //             AddLog($"  Strip #{strip.index}: Y={refY:F4}, rootV={strip.maxV:F4}, yOffset={strip.worldYOffset:F4}");
 //         }
 //     }
 //
 //     private void ExportDetailedLog()
 //     {
 //         string path = EditorUtility.SaveFilePanel("保存详细日志", "", 
 //             $"HairAnalysis_Log_{System.DateTime.Now:yyyyMMdd_HHmmss}", "txt");
 //         
 //         if (string.IsNullOrEmpty(path)) return;
 //         
 //         var sb = new System.Text.StringBuilder();
 //         sb.AppendLine("========== 毛发分析详细日志 ==========");
 //         sb.AppendLine($"时间: {System.DateTime.Now}");
 //         sb.AppendLine($"物体: {targetObject?.name}");
 //         sb.AppendLine($"Mesh: {analyzedMesh?.name}");
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 参数设置 ----------");
 //         sb.AppendLine($"分析方法: {analysisMethod}");
 //         sb.AppendLine($"根部阈值: {rootThreshold}");
 //         sb.AppendLine($"UV连续性阈值: {uvContinuityThreshold}");
 //         sb.AppendLine($"UV差值模式: {uvDifferenceMode}");
 //         sb.AppendLine($"世界Y修正: {enableWorldYCorrection}");
 //         if (enableWorldYCorrection)
 //         {
 //             sb.AppendLine($"  修正模式: {worldYCorrectionMode}");
 //             sb.AppendLine($"  修正权重: {worldYCorrectionWeight}");
 //             sb.AppendLine($"  使用根部Y: {useRootWorldY}");
 //         }
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 排除统计 ----------");
 //         foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
 //         {
 //             sb.AppendLine($"{kvp.Key}: {kvp.Value}");
 //         }
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 详细日志 ----------");
 //         foreach (var log in detailedLogs)
 //         {
 //             sb.AppendLine(log);
 //         }
 //         
 //         System.IO.File.WriteAllText(path, sb.ToString());
 //         Debug.Log($"✓ 详细日志已保存到: {path}");
 //     }
 //
 //     /// <summary>
 //     /// 基于UV分析（改进版：先分组再找根部）
 //     /// </summary>
 //     private void AnalyzeByUV()
 //     {
 //         Vector2[] uvs = analyzedMesh.uv;
 //         Vector3[] vertices = analyzedMesh.vertices;
 //         int[] triangles = analyzedMesh.triangles;
 //
 //         if (uvs == null || uvs.Length == 0)
 //         {
 //             EditorUtility.DisplayDialog("错误", "Mesh没有UV数据", "确定");
 //             return;
 //         }
 //
 //         AddLog("========== 改进版UV分析：先分组再找根部 ==========");
 //
 //         // 第一步：按几何连通性分组
 //         var geometryGroups = FindConnectedComponents(triangles, analyzedMesh.vertexCount);
 //         AddLog($"几何分组完成，共 {geometryGroups.Count} 个独立组");
 //
 //         // 第二步：在每个组内找根部并构建Strip
 //         var adjacency = BuildAdjacencyList(triangles, analyzedMesh.vertexCount);
 //         var vertexToTriangles = BuildVertexToTrianglesMap(triangles);
 //
 //         int stripIndex = 0;
 //         int skippedTooSmall = 0;
 //         int skippedNoVRange = 0;
 //         int skippedNoTriangles = 0;
 //
 //         for (int groupIdx = 0; groupIdx < geometryGroups.Count; groupIdx++)
 //         {
 //             var group = geometryGroups[groupIdx];
 //
 //             if (group.Count < 3)
 //             {
 //                 skippedTooSmall++;
 //                 continue;
 //             }
 //
 //             // 在组内找V值最大/最小的顶点
 //             int rootVert = -1;
 //             float maxV = float.MinValue;
 //             int tipVert = -1;
 //             float minV = float.MaxValue;
 //
 //             foreach (int vertIdx in group)
 //             {
 //                 float v = uvs[vertIdx].y;
 //                 if (v > maxV) { maxV = v; rootVert = vertIdx; }
 //                 if (v < minV) { minV = v; tipVert = vertIdx; }
 //             }
 //
 //             float groupVRange = maxV - minV;
 //
 //             if (groupVRange < 0.01f)
 //             {
 //                 skippedNoVRange++;
 //                 continue;
 //             }
 //
 //             // 创建Strip
 //             HairStrip strip = new HairStrip { index = stripIndex };
 //             strip.vertexIndices = group.ToList();
 //
 //             // 收集三角形
 //             HashSet<int> groupTriangles = new HashSet<int>();
 //             foreach (int vertIdx in group)
 //             {
 //                 if (vertexToTriangles.ContainsKey(vertIdx))
 //                 {
 //                     foreach (int triIdx in vertexToTriangles[vertIdx])
 //                     {
 //                         groupTriangles.Add(triIdx);
 //                     }
 //                 }
 //             }
 //
 //             foreach (int triIdx in groupTriangles)
 //             {
 //                 int baseIdx = triIdx * 3;
 //                 int v0 = triangles[baseIdx];
 //                 int v1 = triangles[baseIdx + 1];
 //                 int v2 = triangles[baseIdx + 2];
 //
 //                 if (group.Contains(v0) && group.Contains(v1) && group.Contains(v2))
 //                 {
 //                     strip.triangleIndices.Add(v0);
 //                     strip.triangleIndices.Add(v1);
 //                     strip.triangleIndices.Add(v2);
 //                 }
 //             }
 //
 //             strip.minV = minV;
 //             strip.maxV = maxV;
 //             strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootVert]);
 //             strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipVert]);
 //
 //             if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
 //             {
 //                 hairStrips.Add(strip);
 //                 stripIndex++;
 //             }
 //             else
 //             {
 //                 skippedNoTriangles++;
 //             }
 //         }
 //
 //         // 更新统计
 //         exclusionStats.Clear();
 //         if (skippedTooSmall > 0) exclusionStats["组太小(<3顶点)"] = skippedTooSmall;
 //         if (skippedNoVRange > 0) exclusionStats["组V值跨度太小(<0.01)"] = skippedNoVRange;
 //         if (skippedNoTriangles > 0) exclusionStats["有效三角形不足"] = skippedNoTriangles;
 //         exclusionStats["有效毛发片"] = hairStrips.Count;
 //     }
 //
 //     private List<HashSet<int>> FindConnectedComponents(int[] triangles, int vertexCount)
 //     {
 //         var adjacency = new Dictionary<int, HashSet<int>>();
 //         for (int i = 0; i < vertexCount; i++)
 //             adjacency[i] = new HashSet<int>();
 //
 //         for (int i = 0; i < triangles.Length; i += 3)
 //         {
 //             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
 //             adjacency[v0].Add(v1); adjacency[v0].Add(v2);
 //             adjacency[v1].Add(v0); adjacency[v1].Add(v2);
 //             adjacency[v2].Add(v0); adjacency[v2].Add(v1);
 //         }
 //
 //         var visited = new HashSet<int>();
 //         var components = new List<HashSet<int>>();
 //
 //         for (int i = 0; i < vertexCount; i++)
 //         {
 //             if (visited.Contains(i) || adjacency[i].Count == 0)
 //             {
 //                 visited.Add(i);
 //                 continue;
 //             }
 //
 //             var component = new HashSet<int>();
 //             var queue = new Queue<int>();
 //             queue.Enqueue(i);
 //
 //             while (queue.Count > 0)
 //             {
 //                 int current = queue.Dequeue();
 //                 if (visited.Contains(current)) continue;
 //
 //                 visited.Add(current);
 //                 component.Add(current);
 //
 //                 foreach (int neighbor in adjacency[current])
 //                 {
 //                     if (!visited.Contains(neighbor))
 //                         queue.Enqueue(neighbor);
 //                 }
 //             }
 //
 //             if (component.Count > 0)
 //                 components.Add(component);
 //         }
 //
 //         return components;
 //     }
 //
 //     private void AnalyzeByConnectedComponent()
 //     {
 //         int[] triangles = analyzedMesh.triangles;
 //         Vector3[] vertices = analyzedMesh.vertices;
 //         Vector2[] uvs = analyzedMesh.uv;
 //         
 //         var edgeTriangles = new Dictionary<Edge, List<int>>();
 //         
 //         for (int i = 0; i < triangles.Length; i += 3)
 //         {
 //             int triIndex = i / 3;
 //             AddEdgeTriangle(edgeTriangles, triangles[i], triangles[i + 1], triIndex);
 //             AddEdgeTriangle(edgeTriangles, triangles[i + 1], triangles[i + 2], triIndex);
 //             AddEdgeTriangle(edgeTriangles, triangles[i + 2], triangles[i], triIndex);
 //         }
 //         
 //         int totalTriangles = triangles.Length / 3;
 //         UnionFind uf = new UnionFind(totalTriangles);
 //         
 //         foreach (var kvp in edgeTriangles)
 //         {
 //             var tris = kvp.Value;
 //             for (int i = 0; i < tris.Count - 1; i++)
 //             {
 //                 for (int j = i + 1; j < tris.Count; j++)
 //                 {
 //                     uf.Union(tris[i], tris[j]);
 //                 }
 //             }
 //         }
 //         
 //         var groups = new Dictionary<int, List<int>>();
 //         for (int i = 0; i < totalTriangles; i++)
 //         {
 //             int root = uf.Find(i);
 //             if (!groups.ContainsKey(root))
 //                 groups[root] = new List<int>();
 //             groups[root].Add(i);
 //         }
 //         
 //         int stripIndex = 0;
 //         foreach (var group in groups.Values)
 //         {
 //             HairStrip strip = new HairStrip { index = stripIndex++ };
 //             HashSet<int> vertSet = new HashSet<int>();
 //             
 //             foreach (int triIdx in group)
 //             {
 //                 int baseIdx = triIdx * 3;
 //                 strip.triangleIndices.Add(triangles[baseIdx]);
 //                 strip.triangleIndices.Add(triangles[baseIdx + 1]);
 //                 strip.triangleIndices.Add(triangles[baseIdx + 2]);
 //                 
 //                 vertSet.Add(triangles[baseIdx]);
 //                 vertSet.Add(triangles[baseIdx + 1]);
 //                 vertSet.Add(triangles[baseIdx + 2]);
 //             }
 //             
 //             strip.vertexIndices = vertSet.ToList();
 //             
 //             if (uvs != null && uvs.Length > 0 && strip.vertexIndices.Count > 0)
 //             {
 //                 strip.minV = strip.vertexIndices.Min(v => uvs[v].y);
 //                 strip.maxV = strip.vertexIndices.Max(v => uvs[v].y);
 //                 
 //                 int rootIdx = strip.vertexIndices.OrderByDescending(v => uvs[v].y).First();
 //                 int tipIdx = strip.vertexIndices.OrderBy(v => uvs[v].y).First();
 //                 
 //                 strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootIdx]);
 //                 strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipIdx]);
 //             }
 //             
 //             hairStrips.Add(strip);
 //         }
 //     }
 //
 //     private void OnSceneGUI(SceneView sceneView)
 //     {
 //         if (!analysisComplete || targetObject == null || hairStrips.Count == 0 || analyzedMesh == null)
 //             return;
 //         
 //         Vector3[] vertices = analyzedMesh.vertices;
 //         Vector2[] uvs = analyzedMesh.uv;
 //         Transform transform = targetObject.transform;
 //         
 //         Handles.matrix = Matrix4x4.identity;
 //         
 //         if (showAllStrips)
 //         {
 //             foreach (var strip in hairStrips)
 //             {
 //                 float alpha = strip.index == currentStripIndex ? 1f : 0.2f;
 //                 DrawStrip(strip, vertices, uvs, transform, alpha);
 //             }
 //         }
 //         else if (currentStripIndex < hairStrips.Count)
 //         {
 //             DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
 //         }
 //     }
 //
 //     private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
 //     {
 //         Color stripColor = strip.debugColor;
 //         
 //         // 绘制三角形面
 //         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
 //         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
 //         {
 //             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
 //             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
 //             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
 //             Handles.DrawAAConvexPolygon(v0, v1, v2);
 //         }
 //         
 //         // 绘制边
 //         Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.8f);
 //         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
 //         {
 //             Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
 //             Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
 //             Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
 //             Handles.DrawLine(v0, v1);
 //             Handles.DrawLine(v1, v2);
 //             Handles.DrawLine(v2, v0);
 //         }
 //         
 //         // 绘制顶点
 //         foreach (int vertIdx in strip.vertexIndices)
 //         {
 //             Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
 //             float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;
 //             
 //             // 计算最终值（包含Y修正）
 //             float finalValue = CalculateFinalBValue(vValue, strip);
 //             
 //             // 着色：根部(高值)=绿色，尖端(低值)=红色
 //             Color vertColor = Color.Lerp(Color.red, Color.green, Mathf.Clamp01(finalValue));
 //             vertColor.a = alpha;
 //             
 //             Handles.color = vertColor;
 //             Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);
 //             
 //             // 标签
 //             if ((showVertexLabels || showUVInfo) && alpha > 0.5f)
 //             {
 //                 string label = "";
 //                 if (showVertexLabels) label += $"[{vertIdx}]";
 //                 if (showUVInfo)
 //                 {
 //                     label += $" V:{vValue:F3}";
 //                     if (enableWorldYCorrection)
 //                     {
 //                         label += $" B:{finalValue:F2}";
 //                     }
 //                 }
 //                 Handles.Label(worldPos + Vector3.up * vertexSphereSize * 1.5f, label, EditorStyles.miniLabel);
 //             }
 //         }
 //         
 //         // 绘制根部和尖端标记
 //         if (showRootTipMarkers && alpha > 0.5f)
 //         {
 //             float rootFinal = CalculateFinalBValue(strip.maxV, strip);
 //             float tipFinal = CalculateFinalBValue(strip.minV, strip);
 //             
 //             // ROOT标记
 //             Handles.color = Color.green;
 //             Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
 //             
 //             string rootLabel = $"ROOT\nV={strip.maxV:F3}\nB={rootFinal:F3}";
 //             if (enableWorldYCorrection)
 //             {
 //                 rootLabel += $"\nY={strip.rootWorldY:F2}\nyOff={strip.worldYOffset:F2}";
 //             }
 //             Handles.Label(strip.rootPosition + Vector3.up * vertexSphereSize * 3f, rootLabel, EditorStyles.whiteBoldLabel);
 //             
 //             // TIP标记
 //             Handles.color = Color.red;
 //             Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);
 //             
 //             string tipLabel = $"TIP\nV={strip.minV:F3}\nB={tipFinal:F3}";
 //             Handles.Label(strip.tipPosition + Vector3.up * vertexSphereSize * 3f, tipLabel, EditorStyles.whiteBoldLabel);
 //             
 //             // 连接线
 //             Handles.color = Color.yellow;
 //             Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 3f);
 //         }
 //     }
 //
 //     private void FocusOnStrip(int index)
 //     {
 //         if (index >= hairStrips.Count) return;
 //         
 //         var strip = hairStrips[index];
 //         Vector3 center = (strip.rootPosition + strip.tipPosition) / 2f;
 //         float size = Mathf.Max(Vector3.Distance(strip.rootPosition, strip.tipPosition) * 3f, 0.1f);
 //         
 //         SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, size);
 //         SceneView.RepaintAll();
 //     }
 //
 //     /// <summary>
 //     /// 生成带UV差值的Mesh（包含Y修正）
 //     /// </summary>
 //     private void GenerateMeshWithUVDifference()
 //     {
 //         Mesh newMesh = Instantiate(analyzedMesh);
 //         
 //         string meshName = analyzedMesh.name + $"_UVDiff_{uvDifferenceMode}";
 //         if (enableWorldYCorrection)
 //         {
 //             meshName += $"_YCorr_{worldYCorrectionMode}";
 //         }
 //         newMesh.name = meshName;
 //         
 //         Vector2[] uvs = newMesh.uv;
 //         Color[] colors = new Color[newMesh.vertexCount];
 //         
 //         // 初始化
 //         for (int i = 0; i < colors.Length; i++)
 //             colors[i] = new Color(1, 1, 0, 1);
 //         
 //         // 创建顶点到毛发片的映射
 //         Dictionary<int, HairStrip> vertexToStrip = new Dictionary<int, HairStrip>();
 //         foreach (var strip in hairStrips)
 //         {
 //             foreach (int vertIdx in strip.vertexIndices)
 //             {
 //                 if (!vertexToStrip.ContainsKey(vertIdx))
 //                 {
 //                     vertexToStrip[vertIdx] = strip;
 //                 }
 //             }
 //         }
 //         
 //         // 计算每个顶点的最终B值
 //         for (int i = 0; i < colors.Length; i++)
 //         {
 //             float v = uvs[i].y;
 //             float finalB = 0f;
 //             
 //             if (vertexToStrip.ContainsKey(i))
 //             {
 //                 HairStrip strip = vertexToStrip[i];
 //                 finalB = CalculateFinalBValue(v, strip);
 //             }
 //             else
 //             {
 //                 // 未分配的顶点使用全局归一化
 //                 finalB = globalVRange > 0.001f ? (v - globalMinV) / globalVRange : 0f;
 //             }
 //             
 //             colors[i].b = finalB*0.5f+0.5f;
 //         }
 //         
 //         newMesh.colors = colors;
 //         
 //         // 应用并保存
 //         ApplyMesh(newMesh);
 //         
 //         string path = EditorUtility.SaveFilePanelInProject(
 //             "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");
 //         
 //         if (!string.IsNullOrEmpty(path))
 //         {
 //             AssetDatabase.CreateAsset(newMesh, path);
 //             AssetDatabase.SaveAssets();
 //             Debug.Log($"✓ Mesh已保存: {path}");
 //             Debug.Log($"  UV差值模式: {uvDifferenceMode}");
 //             if (enableWorldYCorrection)
 //             {
 //                 Debug.Log($"  世界Y修正: {worldYCorrectionMode}, 权重: {worldYCorrectionWeight}");
 //             }
 //             Debug.Log("  UV差值已存储到顶点颜色B通道");
 //         }
 //     }
 //     
 //     private void ExportSingleStrip(HairStrip strip)
 //     {
 //         if (strip == null || strip.vertexIndices == null || strip.vertexIndices.Count < 2)
 //         {
 //             EditorUtility.DisplayDialog("错误", "毛发片数据无效", "确定");
 //             return;
 //         }
 //
 //         try
 //         {
 //             Mesh mesh = CreateMeshFromStrip(strip);
 //             
 //             if (mesh == null || mesh.vertexCount == 0)
 //             {
 //                 EditorUtility.DisplayDialog("错误", "生成Mesh失败", "确定");
 //                 return;
 //             }
 //             
 //             string meshName = $"HairStrip_{strip.index}_{uvDifferenceMode}";
 //             if (enableWorldYCorrection)
 //             {
 //                 meshName += $"_YCorr";
 //             }
 //             
 //             string path = EditorUtility.SaveFilePanelInProject(
 //                 "保存毛发片", meshName, "asset", "选择保存位置");
 //             
 //             if (!string.IsNullOrEmpty(path))
 //             {
 //                 if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
 //                 {
 //                     AssetDatabase.DeleteAsset(path);
 //                 }
 //                 
 //                 AssetDatabase.CreateAsset(mesh, path);
 //                 AssetDatabase.SaveAssets();
 //                 
 //                 Debug.Log($"✓ 毛发片 #{strip.index} 已导出到: {path}");
 //             }
 //         }
 //         catch (System.Exception e)
 //         {
 //             EditorUtility.DisplayDialog("导出失败", $"错误: {e.Message}", "确定");
 //         }
 //     }
 //
 //     private void ExportAllStrips()
 //     {
 //         string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
 //         if (string.IsNullOrEmpty(folder)) return;
 //
 //         if (folder.StartsWith(Application.dataPath))
 //         {
 //             folder = "Assets" + folder.Substring(Application.dataPath.Length);
 //         }
 //
 //         int successCount = 0;
 //         int failCount = 0;
 //
 //         try
 //         {
 //             for (int i = 0; i < hairStrips.Count; i++)
 //             {
 //                 var strip = hairStrips[i];
 //
 //                 bool cancel = EditorUtility.DisplayCancelableProgressBar(
 //                     "导出毛发片",
 //                     $"正在导出 {i + 1}/{hairStrips.Count}",
 //                     (float)i / hairStrips.Count);
 //
 //                 if (cancel) break;
 //
 //                 try
 //                 {
 //                     Mesh mesh = CreateMeshFromStrip(strip);
 //
 //                     if (mesh != null && mesh.vertexCount > 0)
 //                     {
 //                         string path = $"{folder}/HairStrip_{strip.index}.asset";
 //                         if (AssetDatabase.LoadAssetAtPath<Mesh>(path) != null)
 //                         {
 //                             AssetDatabase.DeleteAsset(path);
 //                         }
 //                         AssetDatabase.CreateAsset(mesh, path);
 //                         successCount++;
 //                     }
 //                     else
 //                     {
 //                         failCount++;
 //                     }
 //                 }
 //                 catch
 //                 {
 //                     failCount++;
 //                 }
 //             }
 //         }
 //         finally
 //         {
 //             EditorUtility.ClearProgressBar();
 //         }
 //
 //         AssetDatabase.SaveAssets();
 //         AssetDatabase.Refresh();
 //
 //         EditorUtility.DisplayDialog("导出结果", 
 //             $"导出完成！\n成功: {successCount}\n失败: {failCount}", "确定");
 //     }
 //
 //     private void ExportAnalysisReport()
 //     {
 //         string path = EditorUtility.SaveFilePanel("保存分析报告", "", "HairAnalysisReport", "txt");
 //         if (string.IsNullOrEmpty(path)) return;
 //         
 //         var sb = new System.Text.StringBuilder();
 //         sb.AppendLine("========== 毛发分析报告 ==========");
 //         sb.AppendLine($"物体: {targetObject.name}");
 //         sb.AppendLine($"Mesh: {analyzedMesh.name}");
 //         sb.AppendLine($"总顶点数: {analyzedMesh.vertexCount}");
 //         sb.AppendLine($"总三角形数: {analyzedMesh.triangles.Length / 3}");
 //         sb.AppendLine($"识别毛发片数: {hairStrips.Count}");
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 全局统计 ----------");
 //         sb.AppendLine($"UV V值范围: {globalMinV:F4} ~ {globalMaxV:F4} (Range={globalVRange:F4})");
 //         
 //         if (enableWorldYCorrection)
 //         {
 //             sb.AppendLine($"世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4} (Range={globalWorldYRange:F4})");
 //         }
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 设置 ----------");
 //         sb.AppendLine($"UV差值模式: {uvDifferenceMode}");
 //         sb.AppendLine($"世界Y修正: {enableWorldYCorrection}");
 //         if (enableWorldYCorrection)
 //         {
 //             sb.AppendLine($"  修正模式: {worldYCorrectionMode}");
 //             sb.AppendLine($"  修正权重: {worldYCorrectionWeight}");
 //             sb.AppendLine($"  使用根部Y: {useRootWorldY}");
 //         }
 //         sb.AppendLine();
 //         
 //         sb.AppendLine("---------- 各毛发片详情 ----------");
 //         
 //         foreach (var strip in hairStrips)
 //         {
 //             float rootDiff = CalculateUVDifference(strip.maxV, strip);
 //             float tipDiff = CalculateUVDifference(strip.minV, strip);
 //             float rootFinal = CalculateFinalBValue(strip.maxV, strip);
 //             float tipFinal = CalculateFinalBValue(strip.minV, strip);
 //             
 //             sb.AppendLine($"\n毛发片 #{strip.index}:");
 //             sb.AppendLine($"  顶点数: {strip.vertexCount}");
 //             sb.AppendLine($"  三角形数: {strip.triangleCount}");
 //             sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4} (跨度:{strip.vRange:F4})");
 //             sb.AppendLine($"  UV差值: 根部={rootDiff:F4}, 尖端={tipDiff:F4}");
 //             
 //             if (enableWorldYCorrection)
 //             {
 //                 sb.AppendLine($"  世界Y: 根部={strip.rootWorldY:F4}, 尖端={strip.tipWorldY:F4}");
 //                 sb.AppendLine($"  Y偏移: {strip.worldYOffset:F4}");
 //                 sb.AppendLine($"  最终B值: 根部={rootFinal:F4}, 尖端={tipFinal:F4}");
 //             }
 //         }
 //         
 //         System.IO.File.WriteAllText(path, sb.ToString());
 //         Debug.Log($"✓ 报告已保存: {path}");
 //     }
 //
 //     /// <summary>
 //     /// 从毛发片创建独立Mesh（包含Y修正）
 //     /// </summary>
 //     private Mesh CreateMeshFromStrip(HairStrip strip)
 //     {
 //         Vector3[] origVerts = analyzedMesh.vertices;
 //         Vector2[] origUVs = analyzedMesh.uv;
 //         Vector3[] origNormals = analyzedMesh.normals;
 //         Color[] origColors = analyzedMesh.colors;
 //
 //         HashSet<int> allVertices = new HashSet<int>(strip.vertexIndices);
 //         for (int i = 0; i < strip.triangleIndices.Count; i++)
 //         {
 //             allVertices.Add(strip.triangleIndices[i]);
 //         }
 //
 //         List<int> finalVertexList = allVertices.ToList();
 //         Dictionary<int, int> remap = new Dictionary<int, int>();
 //         for (int i = 0; i < finalVertexList.Count; i++)
 //         {
 //             remap[finalVertexList[i]] = i;
 //         }
 //
 //         int vertCount = finalVertexList.Count;
 //         Vector3[] newVerts = new Vector3[vertCount];
 //         Vector2[] newUVs = new Vector2[vertCount];
 //         Vector3[] newNormals = new Vector3[vertCount];
 //         Color[] newColors = new Color[vertCount];
 //
 //         for (int i = 0; i < vertCount; i++)
 //         {
 //             int origIdx = finalVertexList[i];
 //
 //             newVerts[i] = origVerts[origIdx];
 //             newUVs[i] = (origUVs != null && origIdx < origUVs.Length) ? origUVs[origIdx] : Vector2.zero;
 //             newNormals[i] = (origNormals != null && origIdx < origNormals.Length) ? origNormals[origIdx] : Vector3.up;
 //             newColors[i] = (origColors != null && origIdx < origColors.Length) ? origColors[origIdx] : Color.white;
 //         }
 //
 //         List<int> newTriangles = new List<int>();
 //         for (int i = 0; i < strip.triangleIndices.Count; i += 3)
 //         {
 //             if (i + 2 < strip.triangleIndices.Count)
 //             {
 //                 int idx0 = strip.triangleIndices[i];
 //                 int idx1 = strip.triangleIndices[i + 1];
 //                 int idx2 = strip.triangleIndices[i + 2];
 //
 //                 if (remap.ContainsKey(idx0) && remap.ContainsKey(idx1) && remap.ContainsKey(idx2))
 //                 {
 //                     newTriangles.Add(remap[idx0]);
 //                     newTriangles.Add(remap[idx1]);
 //                     newTriangles.Add(remap[idx2]);
 //                 }
 //             }
 //         }
 //
 //         // 计算最终B值（包含Y修正）
 //         for (int i = 0; i < vertCount; i++)
 //         {
 //             float v = newUVs[i].y;
 //             float finalB = CalculateFinalBValue(v, strip);
 //             newColors[i].b = finalB*0.5f+0.5f;
 //         }
 //
 //         Mesh mesh = new Mesh();
 //         mesh.name = $"HairStrip_{strip.index}";
 //         mesh.vertices = newVerts;
 //         mesh.uv = newUVs;
 //         mesh.normals = newNormals;
 //         mesh.colors = newColors;
 //
 //         if (newTriangles.Count >= 3)
 //         {
 //             mesh.triangles = newTriangles.ToArray();
 //         }
 //
 //         mesh.RecalculateBounds();
 //         return mesh;
 //     }
 //
 //     #region Helper Methods
 //     
 //     private Mesh GetMesh()
 //     {
 //         if (targetObject == null) return null;
 //         var mf = targetObject.GetComponent<MeshFilter>();
 //         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
 //         return mf?.sharedMesh ?? smr?.sharedMesh;
 //     }
 //     
 //     private void ApplyMesh(Mesh mesh)
 //     {
 //         var mf = targetObject.GetComponent<MeshFilter>();
 //         var smr = targetObject.GetComponent<SkinnedMeshRenderer>();
 //         if (mf != null) mf.sharedMesh = mesh;
 //         else if (smr != null) smr.sharedMesh = mesh;
 //     }
 //     
 //     private Dictionary<int, HashSet<int>> BuildAdjacencyList(int[] triangles, int vertexCount)
 //     {
 //         var adj = new Dictionary<int, HashSet<int>>();
 //         for (int i = 0; i < vertexCount; i++) adj[i] = new HashSet<int>();
 //         
 //         for (int i = 0; i < triangles.Length; i += 3)
 //         {
 //             int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
 //             adj[v0].Add(v1); adj[v0].Add(v2);
 //             adj[v1].Add(v0); adj[v1].Add(v2);
 //             adj[v2].Add(v0); adj[v2].Add(v1);
 //         }
 //         return adj;
 //     }
 //     
 //     private Dictionary<int, List<int>> BuildVertexToTrianglesMap(int[] triangles)
 //     {
 //         var map = new Dictionary<int, List<int>>();
 //         for (int i = 0; i < triangles.Length; i += 3)
 //         {
 //             int triIdx = i / 3;
 //             for (int j = 0; j < 3; j++)
 //             {
 //                 int v = triangles[i + j];
 //                 if (!map.ContainsKey(v)) map[v] = new List<int>();
 //                 map[v].Add(triIdx);
 //             }
 //         }
 //         return map;
 //     }
 //     
 //     private void AddEdgeTriangle(Dictionary<Edge, List<int>> dict, int v0, int v1, int triIndex)
 //     {
 //         Edge edge = new Edge(v0, v1);
 //         if (!dict.ContainsKey(edge)) dict[edge] = new List<int>();
 //         dict[edge].Add(triIndex);
 //     }
 //     
 //     public struct Edge : System.IEquatable<Edge>
 //     {
 //         public int v0, v1;
 //         public Edge(int a, int b) { v0 = Mathf.Min(a, b); v1 = Mathf.Max(a, b); }
 //         public bool Equals(Edge other) => v0 == other.v0 && v1 == other.v1;
 //         public override int GetHashCode() => v0 ^ (v1 << 16);
 //     }
 //     
 //     public class UnionFind
 //     {
 //         private int[] parent, rank;
 //         public UnionFind(int n)
 //         {
 //             parent = new int[n]; rank = new int[n];
 //             for (int i = 0; i < n; i++) parent[i] = i;
 //         }
 //         public int Find(int x) { if (parent[x] != x) parent[x] = Find(parent[x]); return parent[x]; }
 //         public void Union(int x, int y)
 //         {
 //             int px = Find(x), py = Find(y);
 //             if (px == py) return;
 //             if (rank[px] < rank[py]) parent[px] = py;
 //             else if (rank[px] > rank[py]) parent[py] = px;
 //             else { parent[py] = px; rank[px]++; }
 //         }
 //     }
 //     
 //     #endregion
 // }
//---------------------------------支持SkinnedMesh和SubMesh的选择-----------------------
using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

public class HairAnalyzerVisualizerV3 : EditorWindow
{
    private GameObject targetObject;
    private Mesh analyzedMesh;
    private Mesh originalMesh; // 保存原始Mesh引用
    
    // 【新增】SubMesh支持
    private int subMeshCount = 0;
    private bool[] selectedSubMeshes;
    private string[] subMeshNames;
    private bool showSubMeshSettings = true;
    
    // 【新增】SkinnedMesh信息
    private bool isSkinnedMesh = false;
    private SkinnedMeshRenderer skinnedMeshRenderer;
    private MeshFilter meshFilter;
    
    // 分析结果
    private List<HairStrip> hairStrips = new List<HairStrip>();
    private int currentStripIndex = 0;
    
    // 全局UV统计
    private float globalMinV = 0f;
    private float globalMaxV = 1f;
    private float globalVRange = 1f;
    
    // 【新增】全局世界Y统计
    private float globalMinWorldY = 0f;
    private float globalMaxWorldY = 1f;
    private float globalWorldYRange = 1f;
    
    // 可视化设置
    private bool showAllStrips = true;
    private bool showVertexLabels = false;
    private bool showUVInfo = true;
    private bool showRootTipMarkers = true;
    private float vertexSphereSize = 0.002f;
    
    // 分析参数
    private float rootThreshold = 0.05f;
    private float uvContinuityThreshold = 0.3f;
    private AnalysisMethod analysisMethod = AnalysisMethod.UVBased;
    
    // UV差值计算模式
    private UVDifferenceMode uvDifferenceMode = UVDifferenceMode.PerStrip;
    
    // 【新增】世界坐标修正设置
    private bool enableWorldYCorrection = false;
    private WorldYCorrectionMode worldYCorrectionMode = WorldYCorrectionMode.AddToUV;
    private float worldYCorrectionWeight = 1.0f;
    private bool useRootWorldY = true;
    
    // 日志设置
    private bool enableDetailedLog = false;
    private bool logToFile = false;
    private int maxLogEntries = 100;
    
    // 排除统计
    private Dictionary<string, int> exclusionStats = new Dictionary<string, int>();
    private List<string> detailedLogs = new List<string>();
    
    private Vector2 scrollPos;
    private bool analysisComplete = false;
    
    // 【新增】SubMesh到Strip的映射
    private Dictionary<int, List<HairStrip>> subMeshToStrips = new Dictionary<int, List<HairStrip>>();
    
    public enum AnalysisMethod
    {
        UVBased,
        TriangleStrip,
        ConnectedComponent,
        UVIsland
    }
    
    public enum UVDifferenceMode
    {
        [InspectorName("单片独立计算")]
        PerStrip,
        [InspectorName("全局V值计算")]
        GlobalV,
        [InspectorName("全局范围归一化")]
        GlobalRange
    }
    
    public enum WorldYCorrectionMode
    {
        [InspectorName("叠加到UV差值")]
        AddToUV,
        [InspectorName("乘以UV差值")]
        MultiplyUV,
        [InspectorName("作为起始偏移")]
        AsStartOffset,
        [InspectorName("混合模式")]
        Blend
    }

    /// <summary>
    /// 毛发条带数据
    /// </summary>
    public class HairStrip
    {
        public int index;
        public int subMeshIndex; // 【新增】所属SubMesh索引
        public List<int> vertexIndices = new List<int>();
        public List<int> triangleIndices = new List<int>();
        public Color debugColor;
        
        public float minV;
        public float maxV;
        
        public Vector3 rootPosition;
        public Vector3 tipPosition;
        
        public float rootWorldY;
        public float tipWorldY;
        public float avgWorldY;
        public float minWorldY;
        public float maxWorldY;
        public float worldYOffset;
        
        public int vertexCount => vertexIndices.Count;
        public int triangleCount => triangleIndices.Count / 3;
        public float vRange => maxV - minV;
    }

    [MenuItem("Tools/TempByAI/Hair/Hair Analyzer Visualizer V3")]
    public static void ShowWindow()
    {
        var window = GetWindow<HairAnalyzerVisualizerV3>("毛发分析可视化 V3");
        window.minSize = new Vector2(450, 750);
    }

    private void OnEnable()
    {
        SceneView.duringSceneGui += OnSceneGUI;
    }

    private void OnDisable()
    {
        SceneView.duringSceneGui -= OnSceneGUI;
    }

    private void OnGUI()
    {
        scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
        
        DrawHeader();
        DrawInputSection();
        DrawSubMeshSection(); // 【新增】SubMesh选择
        DrawAnalysisSettings();
        DrawWorldYCorrectionSettings();
        DrawLogSettings();
        DrawAnalysisButtons();
        
        if (analysisComplete)
        {
            DrawResultsSection();
            DrawWorldYStatsSection();
            DrawExclusionStats();
            DrawStripNavigator();
            DrawVisualizationSettings();
            DrawExportSection();
        }
        
        EditorGUILayout.EndScrollView();
    }

    private void DrawHeader()
    {
        EditorGUILayout.Space(10);
        
        GUIStyle titleStyle = new GUIStyle(EditorStyles.boldLabel)
        {
            fontSize = 16,
            alignment = TextAnchor.MiddleCenter
        };
        GUILayout.Label("🔍 毛发结构分析与可视化 V3", titleStyle);
        
        EditorGUILayout.Space(5);
        
        EditorGUILayout.HelpBox(
            "V3新增功能：\n" +
            "• 支持 SkinnedMeshRenderer\n" +
            "• 支持 SubMesh 选择性处理\n" +
            "• 只替换选中的SubMesh，保留其他SubMesh不变", 
            MessageType.Info);
        
        EditorGUILayout.Space(10);
    }

    private void DrawInputSection()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("📥 输入", EditorStyles.boldLabel);
        
        EditorGUI.BeginChangeCheck();
        targetObject = (GameObject)EditorGUILayout.ObjectField(
            "目标物体", targetObject, typeof(GameObject), true);
        
        if (EditorGUI.EndChangeCheck())
        {
            analysisComplete = false;
            hairStrips.Clear();
            UpdateMeshInfo();
        }
        
        if (targetObject != null)
        {
            // 显示Mesh类型信息
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Mesh类型:", GUILayout.Width(80));
            
            if (isSkinnedMesh)
            {
                EditorGUILayout.LabelField("SkinnedMeshRenderer", EditorStyles.boldLabel);
            }
            else if (meshFilter != null)
            {
                EditorGUILayout.LabelField("MeshFilter", EditorStyles.boldLabel);
            }
            else
            {
                EditorGUILayout.LabelField("未找到Mesh组件", EditorStyles.miniLabel);
            }
            EditorGUILayout.EndHorizontal();
            
            Mesh mesh = GetMesh();
            if (mesh != null)
            {
                EditorGUILayout.LabelField("Mesh名称", mesh.name);
                EditorGUILayout.LabelField("顶点数", mesh.vertexCount.ToString());
                EditorGUILayout.LabelField("三角形数", (mesh.triangles.Length / 3).ToString());
                EditorGUILayout.LabelField("SubMesh数量", mesh.subMeshCount.ToString());
                
                if (mesh.uv != null && mesh.uv.Length > 0)
                {
                    float minV = mesh.uv.Min(uv => uv.y);
                    float maxV = mesh.uv.Max(uv => uv.y);
                    EditorGUILayout.LabelField("UV V值范围", $"{minV:F3} ~ {maxV:F3}");
                }
                else
                {
                    EditorGUILayout.HelpBox("警告：Mesh没有UV数据！", MessageType.Warning);
                }
                
                // 显示骨骼信息（如果是SkinnedMesh）
                if (isSkinnedMesh && skinnedMeshRenderer != null)
                {
                    EditorGUILayout.LabelField("骨骼数量", skinnedMeshRenderer.bones?.Length.ToString() ?? "0");
                    if (mesh.bindposes != null && mesh.bindposes.Length > 0)
                    {
                        EditorGUILayout.LabelField("BindPose数量", mesh.bindposes.Length.ToString());
                    }
                }
            }
        }
        
        EditorGUILayout.EndVertical();
    }

    /// <summary>
    /// 【新增】SubMesh选择UI
    /// </summary>
    private void DrawSubMeshSection()
    {
        if (targetObject == null || subMeshCount <= 0) return;
        
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        
        showSubMeshSettings = EditorGUILayout.Foldout(showSubMeshSettings, $"📦 SubMesh选择 ({subMeshCount}个)", true);
        
        if (showSubMeshSettings)
        {
            EditorGUILayout.HelpBox(
                "选择要分析和处理的SubMesh。\n" +
                "导出时只会修改选中的SubMesh，其他SubMesh保持原样。", 
                MessageType.None);
            
            EditorGUILayout.Space(3);
            
            // 全选/取消全选按钮
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("全选", GUILayout.Width(60)))
            {
                for (int i = 0; i < selectedSubMeshes.Length; i++)
                    selectedSubMeshes[i] = true;
            }
            if (GUILayout.Button("取消全选", GUILayout.Width(80)))
            {
                for (int i = 0; i < selectedSubMeshes.Length; i++)
                    selectedSubMeshes[i] = false;
            }
            if (GUILayout.Button("反选", GUILayout.Width(60)))
            {
                for (int i = 0; i < selectedSubMeshes.Length; i++)
                    selectedSubMeshes[i] = !selectedSubMeshes[i];
            }
            EditorGUILayout.EndHorizontal();
            
            EditorGUILayout.Space(3);
            
            // 显示每个SubMesh的信息和选择框
            Mesh mesh = GetMesh();
            for (int i = 0; i < subMeshCount; i++)
            {
                EditorGUILayout.BeginHorizontal();
                
                selectedSubMeshes[i] = EditorGUILayout.Toggle(selectedSubMeshes[i], GUILayout.Width(20));
                
                var subMeshDesc = mesh.GetSubMesh(i);
                int triCount = subMeshDesc.indexCount / 3;
                
                string label = $"SubMesh {i}: {triCount} 三角形";
                
                // 如果有材质，显示材质名称
                Renderer renderer = targetObject.GetComponent<Renderer>();
                if (renderer != null && renderer.sharedMaterials != null && i < renderer.sharedMaterials.Length)
                {
                    Material mat = renderer.sharedMaterials[i];
                    if (mat != null)
                    {
                        label += $" [{mat.name}]";
                    }
                }
                
                GUIStyle style = selectedSubMeshes[i] ? EditorStyles.boldLabel : EditorStyles.label;
                EditorGUILayout.LabelField(label, style);
                
                EditorGUILayout.EndHorizontal();
            }
            
            // 显示选中统计
            int selectedCount = selectedSubMeshes.Count(s => s);
            EditorGUILayout.LabelField($"已选择: {selectedCount}/{subMeshCount}", EditorStyles.miniLabel);
        }
        
        EditorGUILayout.EndVertical();
    }

    /// <summary>
    /// 【新增】更新Mesh信息
    /// </summary>
    private void UpdateMeshInfo()
    {
        isSkinnedMesh = false;
        skinnedMeshRenderer = null;
        meshFilter = null;
        subMeshCount = 0;
        selectedSubMeshes = null;
        subMeshNames = null;
        
        if (targetObject == null) return;
        
        // 检测Mesh类型
        skinnedMeshRenderer = targetObject.GetComponent<SkinnedMeshRenderer>();
        meshFilter = targetObject.GetComponent<MeshFilter>();
        
        isSkinnedMesh = skinnedMeshRenderer != null;
        
        Mesh mesh = GetMesh();
        if (mesh != null)
        {
            subMeshCount = mesh.subMeshCount;
            selectedSubMeshes = new bool[subMeshCount];
            subMeshNames = new string[subMeshCount];
            
            // 默认全选
            for (int i = 0; i < subMeshCount; i++)
            {
                selectedSubMeshes[i] = true;
                subMeshNames[i] = $"SubMesh_{i}";
            }
        }
    }

    private void DrawAnalysisSettings()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("⚙️ 分析设置", EditorStyles.boldLabel);
        
        analysisMethod = (AnalysisMethod)EditorGUILayout.EnumPopup("分析方法", analysisMethod);
        
        string methodDesc = "";
        switch (analysisMethod)
        {
            case AnalysisMethod.UVBased:
                methodDesc = "从V值最大的点(根部)出发，沿V递减方向追踪";
                break;
            case AnalysisMethod.TriangleStrip:
                methodDesc = "通过共享边的三角形分组";
                break;
            case AnalysisMethod.ConnectedComponent:
                methodDesc = "完全独立的三角形组为一片";
                break;
            case AnalysisMethod.UVIsland:
                methodDesc = "基于UV孤岛分组（推荐）\n✓ 同一顶点不同UV会被正确分离";
                break;
        }
        EditorGUILayout.HelpBox(methodDesc, MessageType.None);
        
        rootThreshold = EditorGUILayout.Slider("根部阈值", rootThreshold, 0.001f, 0.2f);
        uvContinuityThreshold = EditorGUILayout.Slider("UV连续性阈值", uvContinuityThreshold, 0.0001f, 0.2f);
        EditorGUILayout.HelpBox("UV坐标差异小于此值视为同一点\n值越小分组越精细", MessageType.None);
        
        EditorGUILayout.Space(5);
        EditorGUILayout.LabelField("UV差值计算", EditorStyles.boldLabel);
        
        uvDifferenceMode = (UVDifferenceMode)EditorGUILayout.EnumPopup("计算模式", uvDifferenceMode);
        
        string modeDesc = "";
        switch (uvDifferenceMode)
        {
            case UVDifferenceMode.PerStrip:
                modeDesc = "每片毛发独立归一化\ndiff = (V - 片内minV) / 片内vRange\n根部=1, 尖端=0";
                break;
            case UVDifferenceMode.GlobalV:
                modeDesc = "统一根部起点（全局maxV）\ndiff = (全局maxV - 片内maxV) \n根部=1, 尖端=0";
                break;
            case UVDifferenceMode.GlobalRange:
                modeDesc = "使用全局V范围归一化\ndiff = (V - 全局minV) / 全局vRange\n根部=1, 尖端=0";
                break;
        }
        EditorGUILayout.HelpBox(modeDesc, MessageType.None);
        
        EditorGUILayout.EndVertical();
    }

    private void DrawWorldYCorrectionSettings()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");

        EditorGUILayout.BeginHorizontal();
        GUILayout.Label("🌍 世界坐标Y修正", EditorStyles.boldLabel);
        enableWorldYCorrection = EditorGUILayout.Toggle(enableWorldYCorrection, GUILayout.Width(20));
        EditorGUILayout.EndHorizontal();

        if (enableWorldYCorrection)
        {
            EditorGUI.indentLevel++;

            worldYCorrectionMode = (WorldYCorrectionMode)EditorGUILayout.EnumPopup("修正模式", worldYCorrectionMode);

            string correctionDesc = "";
            switch (worldYCorrectionMode)
            {
                case WorldYCorrectionMode.AddToUV:
                    correctionDesc = "最终值 = UV差值 + Y偏移 × 权重\n适合：让低处的毛发流光延迟开始";
                    break;
                case WorldYCorrectionMode.MultiplyUV:
                    correctionDesc = "最终值 = UV差值 × (1 + Y偏移 × 权重)\n适合：低处毛发流光速度调整";
                    break;
                case WorldYCorrectionMode.AsStartOffset:
                    correctionDesc = "最终值 = UV差值 + Y偏移(仅根部)\n适合：不同高度毛发分批启动";
                    break;
                case WorldYCorrectionMode.Blend:
                    correctionDesc = "最终值 = lerp(UV差值, Y偏移, 权重)\n适合：部分依赖位置的流光";
                    break;
            }

            EditorGUILayout.HelpBox(correctionDesc, MessageType.None);

            worldYCorrectionWeight = EditorGUILayout.Slider("修正权重", worldYCorrectionWeight, 0f, 2f);

            useRootWorldY = EditorGUILayout.Toggle("使用根部Y坐标", useRootWorldY);
            if (!useRootWorldY)
            {
                EditorGUILayout.LabelField("  (将使用Strip平均Y坐标)", EditorStyles.miniLabel);
            }

            EditorGUI.indentLevel--;
        }

        EditorGUILayout.EndVertical();
    }

    private void DrawWorldYStatsSection()
    {
        if (!enableWorldYCorrection) return;

        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("🌍 世界Y坐标统计", EditorStyles.boldLabel);

        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField($"全局 Min Y: {globalMinWorldY:F4}", GUILayout.Width(180));
        EditorGUILayout.LabelField($"全局 Max Y: {globalMaxWorldY:F4}");
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.LabelField($"全局 Y Range: {globalWorldYRange:F4}");

        if (hairStrips.Count > 0)
        {
            EditorGUILayout.Space(3);
            
            float rootUVMin = hairStrips.Min(s => s.maxV);
            float rootUVMax = hairStrips.Max(s => s.maxV);
            float rootUVRange = rootUVMax - rootUVMin;
            EditorGUILayout.LabelField($"根节点UV范围: {rootUVMin:F4} ~ {rootUVMax:F4} (Range={rootUVRange:F4})");

            var yOffsets = hairStrips.Select(s => s.worldYOffset).ToList();
            EditorGUILayout.LabelField($"Strip Y偏移范围: {yOffsets.Min():F4} ~ {yOffsets.Max():F4}");
        }

        EditorGUILayout.EndVertical();
    }

    private void DrawLogSettings()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("📋 日志设置", EditorStyles.boldLabel);
        
        enableDetailedLog = EditorGUILayout.Toggle("启用详细日志", enableDetailedLog);
        
        if (enableDetailedLog)
        {
            EditorGUI.indentLevel++;
            maxLogEntries = EditorGUILayout.IntSlider("控制台最大条数", maxLogEntries, 10, 500);
            logToFile = EditorGUILayout.Toggle("同时输出到文件", logToFile);
            EditorGUI.indentLevel--;
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawExclusionStats()
    {
        if (exclusionStats.Count == 0) return;
        
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("📊 顶点排除统计", EditorStyles.boldLabel);
        
        foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
        {
            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField(kvp.Key, GUILayout.Width(250));
            EditorGUILayout.LabelField(kvp.Value.ToString(), EditorStyles.boldLabel);
            EditorGUILayout.EndHorizontal();
        }
        
        EditorGUILayout.Space(3);
        if (GUILayout.Button("导出详细日志"))
        {
            ExportDetailedLog();
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawAnalysisButtons()
    {
        EditorGUILayout.Space(10);
        
        bool hasSelectedSubMesh = selectedSubMeshes != null && selectedSubMeshes.Any(s => s);
        GUI.enabled = targetObject != null && GetMesh() != null && hasSelectedSubMesh;
        
        if (!hasSelectedSubMesh && targetObject != null && GetMesh() != null)
        {
            EditorGUILayout.HelpBox("请至少选择一个SubMesh进行分析", MessageType.Warning);
        }
        
        GUI.backgroundColor = new Color(0.4f, 0.8f, 0.4f);
        if (GUILayout.Button("🔬 开始分析", GUILayout.Height(35)))
        {
            PerformAnalysis();
        }
        GUI.backgroundColor = Color.white;
        
        GUI.enabled = true;
    }

    private void DrawResultsSection()
    {
        EditorGUILayout.Space(10);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("📊 分析结果", EditorStyles.boldLabel);
        
        EditorGUILayout.LabelField("识别到的毛发片", hairStrips.Count.ToString());
        // 显示分析方法
        EditorGUILayout.LabelField("分析方法", analysisMethod.ToString());
    
        // UV孤岛模式显示节点数
        if (analysisMethod == AnalysisMethod.UVIsland && totalUVNodes > 0)
        {
            EditorGUILayout.LabelField("UV节点数", $"{totalUVNodes} (原顶点: {analyzedMesh.vertexCount})");
        }
        // 显示每个SubMesh的Strip数量
        if (subMeshToStrips.Count > 0)
        {
            EditorGUILayout.Space(3);
            EditorGUILayout.LabelField("各SubMesh分布:", EditorStyles.miniBoldLabel);
            foreach (var kvp in subMeshToStrips.OrderBy(x => x.Key))
            {
                EditorGUILayout.LabelField($"  SubMesh {kvp.Key}: {kvp.Value.Count} 片");
            }
        }
        
        EditorGUILayout.Space(3);
        EditorGUILayout.LabelField("全局UV统计", EditorStyles.boldLabel);
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField($"全局 Min V: {globalMinV:F4}", GUILayout.Width(150));
        EditorGUILayout.LabelField($"全局 Max V: {globalMaxV:F4}");
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.LabelField($"全局 V Range: {globalVRange:F4}");
        
        if (hairStrips.Count > 0)
        {
            EditorGUILayout.Space(3);
            var vertexCounts = hairStrips.Select(s => s.vertexCount).ToList();
            var triCounts = hairStrips.Select(s => s.triangleCount).ToList();
            var vRanges = hairStrips.Select(s => s.vRange).ToList();
            
            EditorGUILayout.LabelField("顶点数范围", $"{vertexCounts.Min()} ~ {vertexCounts.Max()} (平均:{vertexCounts.Average():F1})");
            EditorGUILayout.LabelField("三角形数范围", $"{triCounts.Min()} ~ {triCounts.Max()}");
            EditorGUILayout.LabelField("单片V值跨度范围", $"{vRanges.Min():F3} ~ {vRanges.Max():F3}");
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawStripNavigator()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("🧭 毛发片导航", EditorStyles.boldLabel);
        
        if (hairStrips.Count > 0)
        {
            EditorGUILayout.BeginHorizontal();
            
            if (GUILayout.Button("◀", GUILayout.Width(40)))
            {
                currentStripIndex = (currentStripIndex - 1 + hairStrips.Count) % hairStrips.Count;
                FocusOnStrip(currentStripIndex);
            }
            
            currentStripIndex = EditorGUILayout.IntSlider(currentStripIndex, 0, hairStrips.Count - 1);
            
            if (GUILayout.Button("▶", GUILayout.Width(40)))
            {
                currentStripIndex = (currentStripIndex + 1) % hairStrips.Count;
                FocusOnStrip(currentStripIndex);
            }
            
            EditorGUILayout.EndHorizontal();
            
            if (currentStripIndex < hairStrips.Count)
            {
                var strip = hairStrips[currentStripIndex];
                
                EditorGUILayout.Space(5);
                EditorGUILayout.BeginVertical("helpbox");
                
                EditorGUILayout.LabelField($"毛发片 #{strip.index} (SubMesh {strip.subMeshIndex})", EditorStyles.boldLabel);
                
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField("顶点数", strip.vertexCount.ToString(), GUILayout.Width(150));
                EditorGUILayout.LabelField("三角形数", strip.triangleCount.ToString());
                EditorGUILayout.EndHorizontal();
                
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField("根部V值(MAX)", $"{strip.maxV:F4}", GUILayout.Width(150));
                EditorGUILayout.LabelField("尖端V值(MIN)", $"{strip.minV:F4}");
                EditorGUILayout.EndHorizontal();
                
                EditorGUILayout.LabelField("V值跨度", $"{strip.vRange:F4}");
                
                if (enableWorldYCorrection)
                {
                    EditorGUILayout.Space(3);
                    EditorGUILayout.LabelField("世界Y坐标", EditorStyles.miniBoldLabel);
                    EditorGUILayout.BeginHorizontal();
                    EditorGUILayout.LabelField($"根部Y: {strip.rootWorldY:F4}", GUILayout.Width(150));
                    EditorGUILayout.LabelField($"尖端Y: {strip.tipWorldY:F4}");
                    EditorGUILayout.EndHorizontal();
                    EditorGUILayout.LabelField($"Y偏移值: {strip.worldYOffset:F4}");
                }
                
                float rootDiff = CalculateUVDifference(strip.maxV, strip);
                float tipDiff = CalculateUVDifference(strip.minV, strip);
                
                if (enableWorldYCorrection)
                {
                    float rootFinal = ApplyWorldYCorrection(rootDiff, strip);
                    float tipFinal = ApplyWorldYCorrection(tipDiff, strip);
                    EditorGUILayout.LabelField($"UV差值: 根部={rootDiff:F3}, 尖端={tipDiff:F3}");
                    EditorGUILayout.LabelField($"最终值(+Y修正): 根部={rootFinal:F3}, 尖端={tipFinal:F3}");
                }
                else
                {
                    EditorGUILayout.LabelField($"差值预览: 根部={rootDiff:F3}, 尖端={tipDiff:F3}");
                }
                
                EditorGUILayout.EndVertical();
                
                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("聚焦此片"))
                {
                    FocusOnStrip(currentStripIndex);
                }
                if (GUILayout.Button("导出此片"))
                {
                    ExportSingleStrip(strip);
                }
                EditorGUILayout.EndHorizontal();
            }
        }
        
        EditorGUILayout.EndVertical();
    }

    private void DrawVisualizationSettings()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("👁 可视化设置", EditorStyles.boldLabel);
        
        showAllStrips = EditorGUILayout.Toggle("显示所有毛发片", showAllStrips);
        showVertexLabels = EditorGUILayout.Toggle("显示顶点索引", showVertexLabels);
        showUVInfo = EditorGUILayout.Toggle("显示UV V值", showUVInfo);
        showRootTipMarkers = EditorGUILayout.Toggle("显示根部/尖端标记", showRootTipMarkers);
        vertexSphereSize = EditorGUILayout.Slider("顶点大小", vertexSphereSize, 0.0005f, 0.02f);
        
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("刷新视图"))
        {
            SceneView.RepaintAll();
        }
        if (GUILayout.Button("重置相机"))
        {
            if (targetObject != null)
            {
                SceneView.lastActiveSceneView?.LookAt(targetObject.transform.position);
            }
        }
        EditorGUILayout.EndHorizontal();
        
        EditorGUILayout.EndVertical();
    }

    private void DrawExportSection()
    {
        EditorGUILayout.Space(5);
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("📤 导出", EditorStyles.boldLabel);
        
        EditorGUILayout.LabelField($"UV差值模式: {uvDifferenceMode}", EditorStyles.miniLabel);
        if (enableWorldYCorrection)
        {
            EditorGUILayout.LabelField($"世界Y修正: {worldYCorrectionMode} (权重:{worldYCorrectionWeight:F2})", EditorStyles.miniLabel);
        }
        
        int selectedCount = selectedSubMeshes?.Count(s => s) ?? 0;
        EditorGUILayout.LabelField($"将处理 {selectedCount}/{subMeshCount} 个SubMesh", EditorStyles.miniLabel);
        
        EditorGUILayout.Space(5);
        
        if (GUILayout.Button("生成带UV差值的Mesh（保留未选SubMesh）"))
        {
            GenerateMeshWithUVDifference();
        }
        
        if (GUILayout.Button("导出所有毛发片"))
        {
            ExportAllStrips();
        }
        
        if (GUILayout.Button("导出分析报告"))
        {
            ExportAnalysisReport();
        }
        
        EditorGUILayout.EndVertical();
    }

    private float CalculateUVDifference(float vValue, HairStrip strip)
    {
        switch (uvDifferenceMode)
        {
            case UVDifferenceMode.PerStrip:
                return strip.vRange > 0.001f ? (vValue - strip.minV) / strip.vRange : 0f;
                
            case UVDifferenceMode.GlobalV:
                return globalMaxV - strip.maxV;
                
            case UVDifferenceMode.GlobalRange:
                return globalVRange > 0.001f ? (vValue - globalMinV) / globalVRange : 0f;
                
            default:
                return 0f;
        }
    }

    private float ApplyWorldYCorrection(float uvDiff, HairStrip strip)
    {
        if (!enableWorldYCorrection)
            return uvDiff;
        
        float yOffset = strip.worldYOffset;
        float weight = worldYCorrectionWeight;
        
        switch (worldYCorrectionMode)
        {
            case WorldYCorrectionMode.AddToUV:
                return uvDiff - yOffset * weight;
                
            case WorldYCorrectionMode.MultiplyUV:
                return uvDiff * (1f - yOffset * weight);
                
            case WorldYCorrectionMode.AsStartOffset:
                float rootInfluence = Mathf.Pow(uvDiff, 2f);
                return uvDiff - yOffset * weight * rootInfluence;
                
            case WorldYCorrectionMode.Blend:
                return Mathf.Lerp(uvDiff, -yOffset, weight);
                
            default:
                return uvDiff;
        }
    }

    private float CalculateFinalBValue(float vValue, HairStrip strip)
    {
        float uvDiff = CalculateUVDifference(vValue, strip);
        return ApplyWorldYCorrection(uvDiff, strip);
    }

    private void AddLog(string message)
    {
        if (!enableDetailedLog) return;
        detailedLogs.Add($"[{System.DateTime.Now:HH:mm:ss.fff}] {message}");
    }

    private void AddExclusionStat(string reason)
    {
        if (!exclusionStats.ContainsKey(reason))
            exclusionStats[reason] = 0;
        exclusionStats[reason]++;
    }

    /// <summary>
/// 执行分析（支持SubMesh）
/// </summary>
private void PerformAnalysis()
{
    originalMesh = GetMesh();
    analyzedMesh = originalMesh;
    
    if (analyzedMesh == null) return;
    
    hairStrips.Clear();
    exclusionStats.Clear();
    detailedLogs.Clear();
    subMeshToStrips.Clear();
    // 清理UV节点映射
    loopToNode.Clear();
    nodeToLoops.Clear();
    nodeToVert.Clear();
    totalUVNodes = 0;
    
    AddLog("========== 开始毛发分析 ==========");
    AddLog($"Mesh: {analyzedMesh.name}, 顶点数: {analyzedMesh.vertexCount}, 三角形数: {analyzedMesh.triangles.Length / 3}");
    AddLog($"SubMesh数量: {subMeshCount}");
    AddLog($"Mesh类型: {(isSkinnedMesh ? "SkinnedMeshRenderer" : "MeshFilter")}");
    
    // 记录选中的SubMesh
    for (int i = 0; i < subMeshCount; i++)
    {
        AddLog($"  SubMesh {i}: {(selectedSubMeshes[i] ? "已选" : "未选")}");
    }
    
    // 计算全局UV统计（仅选中的SubMesh）
    CalculateGlobalUVStats();
    AddLog($"全局UV统计: MinV={globalMinV:F4}, MaxV={globalMaxV:F4}, Range={globalVRange:F4}");
    
    // 对每个选中的SubMesh进行分析
    int stripIndex = 0;
    for (int subMeshIdx = 0; subMeshIdx < subMeshCount; subMeshIdx++)
    {
        if (!selectedSubMeshes[subMeshIdx])
        {
            AddLog($"跳过 SubMesh {subMeshIdx}（未选中）");
            continue;
        }
        
        AddLog($"分析 SubMesh {subMeshIdx}...");
        
        List<HairStrip> subMeshStrips = AnalyzeSubMesh(subMeshIdx, ref stripIndex);
        
        if (subMeshStrips.Count > 0)
        {
            hairStrips.AddRange(subMeshStrips);
            subMeshToStrips[subMeshIdx] = subMeshStrips;
            AddLog($"  SubMesh {subMeshIdx}: 识别到 {subMeshStrips.Count} 个毛发片");
        }
        else
        {
            AddLog($"  SubMesh {subMeshIdx}: 未识别到有效毛发片");
        }
    }
    
    // 计算世界Y统计和偏移
    if (enableWorldYCorrection)
    {
        CalculateWorldYStats();
    }
    
    // 分配随机颜色
    System.Random rand = new System.Random(42);
    foreach (var strip in hairStrips)
    {
        strip.debugColor = Color.HSVToRGB((float)rand.NextDouble(), 0.7f, 0.9f);
    }
    
    // 记录排除统计
    AddLog("");
    AddLog("========== 排除统计 ==========");
    foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
    {
        AddLog($"{kvp.Key}: {kvp.Value}");
    }
    
    // 记录各Strip摘要
    AddLog("");
    AddLog("========== 毛发片摘要 ==========");
    foreach (var strip in hairStrips)
    {
        AddLog($"Strip #{strip.index} (SubMesh {strip.subMeshIndex}): {strip.vertexCount}顶点, {strip.triangleCount}三角形, V={strip.minV:F4}~{strip.maxV:F4}");
    }
    
    analysisComplete = true;
    currentStripIndex = 0;
    
    // ============ 控制台输出 ============
    Debug.Log($"✓ 分析完成！识别到 {hairStrips.Count} 个毛发片");
    Debug.Log($"  处理了 {selectedSubMeshes.Count(s => s)}/{subMeshCount} 个SubMesh");
    Debug.Log($"  全局UV范围: V = {globalMinV:F4} ~ {globalMaxV:F4}");
    
    if (enableWorldYCorrection)
    {
        Debug.Log($"  全局世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4}");
    }
    
    // ============ 详细日志输出 ============
    if (enableDetailedLog)
    {
        // 输出排除统计到控制台
        Debug.Log("---------- 排除统计 ----------");
        foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
        {
            Debug.Log($"  {kvp.Key}: {kvp.Value}");
        }
        
        // 输出部分详细日志到控制台
        int logCount = Mathf.Min(detailedLogs.Count, maxLogEntries);
        Debug.Log($"---------- 详细日志 (显示前{logCount}条，共{detailedLogs.Count}条) ----------");
        for (int i = 0; i < logCount; i++)
        {
            Debug.Log(detailedLogs[i]);
        }
        
        if (detailedLogs.Count > maxLogEntries)
        {
            Debug.Log($"... 省略了 {detailedLogs.Count - maxLogEntries} 条日志");
        }
        
        // 【修复】同时输出到文件
        if (logToFile)
        {
            AutoExportLogToFile();
        }
    }
    
    SceneView.RepaintAll();
}

    /// <summary>
    /// 【新增】自动导出日志到文件
    /// </summary>
    private void AutoExportLogToFile()
    {
        try
        {
            // 自动生成文件路径
            string directory = System.IO.Path.Combine(Application.dataPath, "../Logs");
            if (!System.IO.Directory.Exists(directory))
            {
                System.IO.Directory.CreateDirectory(directory);
            }

            string fileName = $"HairAnalysis_{targetObject.name}_{System.DateTime.Now:yyyyMMdd_HHmmss}.txt";
            string path = System.IO.Path.Combine(directory, fileName);

            var sb = new System.Text.StringBuilder();
            sb.AppendLine("========== 毛发分析详细日志 ==========");
            sb.AppendLine($"时间: {System.DateTime.Now}");
            sb.AppendLine($"物体: {targetObject?.name}");
            sb.AppendLine($"Mesh: {analyzedMesh?.name}");
            sb.AppendLine($"Mesh类型: {(isSkinnedMesh ? "SkinnedMeshRenderer" : "MeshFilter")}");
            sb.AppendLine($"SubMesh数量: {subMeshCount}");
            sb.AppendLine();

            sb.AppendLine("---------- 参数设置 ----------");
            sb.AppendLine($"分析方法: {analysisMethod}");
            sb.AppendLine($"根部阈值: {rootThreshold}");
            sb.AppendLine($"UV连续性阈值: {uvContinuityThreshold}");
            sb.AppendLine($"UV差值模式: {uvDifferenceMode}");
            sb.AppendLine($"世界Y修正: {enableWorldYCorrection}");
            if (enableWorldYCorrection)
            {
                sb.AppendLine($"  修正模式: {worldYCorrectionMode}");
                sb.AppendLine($"  修正权重: {worldYCorrectionWeight}");
                sb.AppendLine($"  使用根部Y: {useRootWorldY}");
            }

            sb.AppendLine();

            sb.AppendLine("---------- 选中的SubMesh ----------");
            for (int i = 0; i < subMeshCount; i++)
            {
                var desc = analyzedMesh.GetSubMesh(i);
                string status = selectedSubMeshes[i] ? "已选" : "未选";
                int stripCount = subMeshToStrips.ContainsKey(i) ? subMeshToStrips[i].Count : 0;
                sb.AppendLine($"SubMesh {i}: {status} ({desc.indexCount / 3} 三角形, {stripCount} 毛发片)");
            }

            sb.AppendLine();

            sb.AppendLine("---------- 全局统计 ----------");
            sb.AppendLine($"识别毛发片总数: {hairStrips.Count}");
            sb.AppendLine($"UV V值范围: {globalMinV:F4} ~ {globalMaxV:F4} (Range={globalVRange:F4})");
            if (enableWorldYCorrection)
            {
                sb.AppendLine($"世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4} (Range={globalWorldYRange:F4})");
            }

            sb.AppendLine();

            sb.AppendLine("---------- 排除统计 ----------");
            foreach (var kvp in exclusionStats.OrderByDescending(x => x.Value))
            {
                sb.AppendLine($"{kvp.Key}: {kvp.Value}");
            }

            sb.AppendLine();

            sb.AppendLine("---------- 详细日志 ----------");
            foreach (var log in detailedLogs)
            {
                sb.AppendLine(log);
            }

            sb.AppendLine();

            sb.AppendLine("---------- 毛发片详情 ----------");
            foreach (var strip in hairStrips)
            {
                float rootDiff = CalculateUVDifference(strip.maxV, strip);
                float tipDiff = CalculateUVDifference(strip.minV, strip);
                float rootFinal = CalculateFinalBValue(strip.maxV, strip);
                float tipFinal = CalculateFinalBValue(strip.minV, strip);

                sb.AppendLine($"\n毛发片 #{strip.index} (SubMesh {strip.subMeshIndex}):");
                sb.AppendLine($"  顶点数: {strip.vertexCount}");
                sb.AppendLine($"  三角形数: {strip.triangleCount}");
                sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4} (跨度:{strip.vRange:F4})");
                sb.AppendLine($"  UV差值: 根部={rootDiff:F4}, 尖端={tipDiff:F4}");

                if (enableWorldYCorrection)
                {
                    sb.AppendLine($"  世界Y: 根部={strip.rootWorldY:F4}, 尖端={strip.tipWorldY:F4}");
                    sb.AppendLine($"  Y偏移: {strip.worldYOffset:F4}");
                    sb.AppendLine($"  最终B值: 根部={rootFinal:F4}, 尖端={tipFinal:F4}");
                }

                // 顶点列表预览
                string vertPreview = string.Join(", ", strip.vertexIndices.Take(20));
                if (strip.vertexIndices.Count > 20) vertPreview += $"... (共{strip.vertexIndices.Count}个)";
                sb.AppendLine($"  顶点索引: {vertPreview}");
            }

            System.IO.File.WriteAllText(path, sb.ToString());
            Debug.Log($"✓ 日志已自动保存到: {path}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"自动保存日志失败: {e.Message}");
        }
    }

    // /// <summary>
    // /// 【新增】分析单个SubMesh
    // /// </summary>
    // private List<HairStrip> AnalyzeSubMesh(int subMeshIndex, ref int stripIndex)
    // {
    //     List<HairStrip> strips = new List<HairStrip>();
    //     
    //     var subMeshDesc = analyzedMesh.GetSubMesh(subMeshIndex);
    //     int indexStart = (int)subMeshDesc.indexStart;
    //     int indexCount = (int)subMeshDesc.indexCount;
    //     
    //     // 获取SubMesh的三角形
    //     int[] allTriangles = analyzedMesh.triangles;
    //     int[] subMeshTriangles = new int[indexCount];
    //     System.Array.Copy(allTriangles, indexStart, subMeshTriangles, 0, indexCount);
    //     
    //     Vector2[] uvs = analyzedMesh.uv;
    //     Vector3[] vertices = analyzedMesh.vertices;
    //     
    //     // 找到SubMesh中使用的所有顶点
    //     HashSet<int> subMeshVertices = new HashSet<int>();
    //     for (int i = 0; i < subMeshTriangles.Length; i++)
    //     {
    //         subMeshVertices.Add(subMeshTriangles[i]);
    //     }
    //     
    //     // 按几何连通性分组
    //     var geometryGroups = FindConnectedComponentsInSubMesh(subMeshTriangles, analyzedMesh.vertexCount);
    //     AddLog($"  SubMesh {subMeshIndex}: 几何分组 {geometryGroups.Count} 个");
    //     
    //     foreach (var group in geometryGroups)
    //     {
    //         if (group.Count < 3) continue;
    //         
    //         // 找V值最大/最小的顶点
    //         int rootVert = -1;
    //         float maxV = float.MinValue;
    //         int tipVert = -1;
    //         float minV = float.MaxValue;
    //         
    //         foreach (int vertIdx in group)
    //         {
    //             if (uvs == null || vertIdx >= uvs.Length) continue;
    //             float v = uvs[vertIdx].y;
    //             if (v > maxV) { maxV = v; rootVert = vertIdx; }
    //             if (v < minV) { minV = v; tipVert = vertIdx; }
    //         }
    //         
    //         float groupVRange = maxV - minV;
    //         if (groupVRange < 0.01f) continue;
    //         
    //         // 创建Strip
    //         HairStrip strip = new HairStrip
    //         {
    //             index = stripIndex++,
    //             subMeshIndex = subMeshIndex
    //         };
    //         strip.vertexIndices = group.ToList();
    //         
    //         // 收集三角形
    //         var vertexToTriangles = BuildVertexToTrianglesMapForSubMesh(subMeshTriangles);
    //         HashSet<int> groupTriangles = new HashSet<int>();
    //         
    //         foreach (int vertIdx in group)
    //         {
    //             if (vertexToTriangles.ContainsKey(vertIdx))
    //             {
    //                 foreach (int localTriIdx in vertexToTriangles[vertIdx])
    //                 {
    //                     groupTriangles.Add(localTriIdx);
    //                 }
    //             }
    //         }
    //         
    //         foreach (int localTriIdx in groupTriangles)
    //         {
    //             int baseIdx = localTriIdx * 3;
    //             if (baseIdx + 2 < subMeshTriangles.Length)
    //             {
    //                 int v0 = subMeshTriangles[baseIdx];
    //                 int v1 = subMeshTriangles[baseIdx + 1];
    //                 int v2 = subMeshTriangles[baseIdx + 2];
    //                 
    //                 if (group.Contains(v0) && group.Contains(v1) && group.Contains(v2))
    //                 {
    //                     strip.triangleIndices.Add(v0);
    //                     strip.triangleIndices.Add(v1);
    //                     strip.triangleIndices.Add(v2);
    //                 }
    //             }
    //         }
    //         
    //         strip.minV = minV;
    //         strip.maxV = maxV;
    //         
    //         if (rootVert >= 0)
    //             strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootVert]);
    //         if (tipVert >= 0)
    //             strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipVert]);
    //         
    //         if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
    //         {
    //             strips.Add(strip);
    //         }
    //     }
    //     
    //     return strips;
    // }
    /// <summary>
    /// 分析单个SubMesh（支持UV孤岛模式）
    /// </summary>
    private List<HairStrip> AnalyzeSubMesh(int subMeshIndex, ref int stripIndex)
    {
        List<HairStrip> strips = new List<HairStrip>();

        var subMeshDesc = analyzedMesh.GetSubMesh(subMeshIndex);
        int indexStart = (int)subMeshDesc.indexStart;
        int indexCount = (int)subMeshDesc.indexCount;

        // 获取SubMesh的三角形
        int[] allTriangles = analyzedMesh.triangles;
        int[] subMeshTriangles = new int[indexCount];
        System.Array.Copy(allTriangles, indexStart, subMeshTriangles, 0, indexCount);

        Vector2[] uvs = analyzedMesh.uv;
        Vector3[] vertices = analyzedMesh.vertices;

        List<HashSet<int>> geometryGroups;
        List<HashSet<int>> componentNodesList = null;

        // 根据分析方法选择不同的连通性算法
        if (analysisMethod == AnalysisMethod.UVIsland)
        {
            geometryGroups = FindConnectedComponentsByUVIsland(
                subMeshTriangles,
                uvs,
                uvContinuityThreshold,
                out componentNodesList
            );
            AddLog($"  SubMesh {subMeshIndex}: UV孤岛分组 {geometryGroups.Count} 个");
        }
        else
        {
            // 几何连通性（原有逻辑）
            geometryGroups = FindConnectedComponentsInSubMesh(subMeshTriangles, analyzedMesh.vertexCount);
            AddLog($"  SubMesh {subMeshIndex}: 几何分组 {geometryGroups.Count} 个");
        }

        for (int groupIdx = 0; groupIdx < geometryGroups.Count; groupIdx++)
        {
            var group = geometryGroups[groupIdx];

            if (group.Count < 3)
            {
                AddExclusionStat("顶点数小于3");
                continue;
            }

            // 获取该分量的loop索引集合（如果使用UV孤岛方法）
            HashSet<int> componentLoops = null;
            if (componentNodesList != null && groupIdx < componentNodesList.Count)
            {
                componentLoops = new HashSet<int>();
                foreach (int nodeId in componentNodesList[groupIdx])
                {
                    if (nodeToLoops.ContainsKey(nodeId))
                    {
                        foreach (int loopIdx in nodeToLoops[nodeId])
                        {
                            componentLoops.Add(loopIdx);
                        }
                    }
                }
            }

            // 找V值最大/最小的顶点
            int rootVert = -1;
            float maxV = float.MinValue;
            int tipVert = -1;
            float minV = float.MaxValue;

            if (analysisMethod == AnalysisMethod.UVIsland && componentLoops != null && componentLoops.Count > 0)
            {
                // 使用loop的UV值（更准确）
                foreach (int loopIdx in componentLoops)
                {
                    int localTriIdx = loopIdx / 3;
                    int offset = loopIdx % 3;
                    int baseIdx = localTriIdx * 3;

                    if (baseIdx + offset < subMeshTriangles.Length)
                    {
                        int vertIdx = subMeshTriangles[baseIdx + offset];
                        if (uvs != null && vertIdx < uvs.Length)
                        {
                            float v = uvs[vertIdx].y;
                            if (v > maxV)
                            {
                                maxV = v;
                                rootVert = vertIdx;
                            }

                            if (v < minV)
                            {
                                minV = v;
                                tipVert = vertIdx;
                            }
                        }
                    }
                }
            }
            else
            {
                // 回退到顶点UV
                foreach (int vertIdx in group)
                {
                    if (uvs == null || vertIdx >= uvs.Length) continue;
                    float v = uvs[vertIdx].y;
                    if (v > maxV)
                    {
                        maxV = v;
                        rootVert = vertIdx;
                    }

                    if (v < minV)
                    {
                        minV = v;
                        tipVert = vertIdx;
                    }
                }
            }

            float groupVRange = maxV - minV;

            // 使用 rootThreshold 过滤
            if (groupVRange < rootThreshold)
            {
                AddExclusionStat($"V范围小于阈值({rootThreshold:F3})");
                continue;
            }

            // 创建Strip
            HairStrip strip = new HairStrip
            {
                index = stripIndex++,
                subMeshIndex = subMeshIndex
            };
            strip.vertexIndices = group.ToList();

            // 收集三角形
            var vertexToTriangles = BuildVertexToTrianglesMapForSubMesh(subMeshTriangles);
            HashSet<int> groupTriangles = new HashSet<int>();

            foreach (int vertIdx in group)
            {
                if (vertexToTriangles.ContainsKey(vertIdx))
                {
                    foreach (int localTriIdx in vertexToTriangles[vertIdx])
                    {
                        groupTriangles.Add(localTriIdx);
                    }
                }
            }

            foreach (int localTriIdx in groupTriangles)
            {
                int baseIdx = localTriIdx * 3;
                if (baseIdx + 2 < subMeshTriangles.Length)
                {
                    int v0 = subMeshTriangles[baseIdx];
                    int v1 = subMeshTriangles[baseIdx + 1];
                    int v2 = subMeshTriangles[baseIdx + 2];

                    if (group.Contains(v0) && group.Contains(v1) && group.Contains(v2))
                    {
                        strip.triangleIndices.Add(v0);
                        strip.triangleIndices.Add(v1);
                        strip.triangleIndices.Add(v2);
                    }
                }
            }

            strip.minV = minV;
            strip.maxV = maxV;

            if (rootVert >= 0)
                strip.rootPosition = targetObject.transform.TransformPoint(vertices[rootVert]);
            if (tipVert >= 0)
                strip.tipPosition = targetObject.transform.TransformPoint(vertices[tipVert]);

            if (strip.vertexIndices.Count >= 2 && strip.triangleIndices.Count >= 3)
            {
                strips.Add(strip);
            }
            else
            {
                AddExclusionStat("最终检查不通过");
            }
        }

        return strips;
    }

    /// <summary>
    /// 基于UV孤岛查找连通分量
    /// 相同顶点但不同UV坐标会被视为不同的节点
    /// </summary>
    private List<HashSet<int>> FindConnectedComponentsByUVIsland(
        int[] triangles,
        Vector2[] uvs,
        float uvTolerance,
        out List<HashSet<int>> componentNodesList)
    {
        // 清空映射
        loopToNode.Clear();
        nodeToLoops.Clear();
        nodeToVert.Clear();

        var adjacency = new Dictionary<int, HashSet<int>>(); // node_id -> connected node_ids
        var vertUvToNode = new Dictionary<string, int>(); // "vertIdx_uvXKey_uvYKey" -> node_id

        int nodeIdCounter = 0;

        // 第一遍：为每个三角形顶点创建或分配节点
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int[] triVerts = { triangles[i], triangles[i + 1], triangles[i + 2] };
            int[] triNodes = new int[3];

            for (int j = 0; j < 3; j++)
            {
                int vertIdx = triVerts[j];

                if (uvs == null || vertIdx >= uvs.Length)
                {
                    AddExclusionStat("UV孤岛: 顶点无UV数据");
                    triNodes[j] = -1;
                    continue;
                }

                Vector2 uv = uvs[vertIdx];

                // 将UV坐标量化为key（避免浮点精度问题）
                int uvXKey = Mathf.RoundToInt(uv.x / uvTolerance);
                int uvYKey = Mathf.RoundToInt(uv.y / uvTolerance);

                string lookupKey = $"{vertIdx}_{uvXKey}_{uvYKey}";

                int nodeId;
                if (vertUvToNode.TryGetValue(lookupKey, out nodeId))
                {
                    // 已存在相同顶点+相似UV的节点
                }
                else
                {
                    // 创建新节点
                    nodeId = nodeIdCounter++;
                    vertUvToNode[lookupKey] = nodeId;
                    nodeToVert[nodeId] = vertIdx;
                    nodeToLoops[nodeId] = new List<int>();
                }

                // 记录这个"loop"（三角形顶点位置）到节点的映射
                int loopIdx = i + j;
                loopToNode[loopIdx] = nodeId;
                nodeToLoops[nodeId].Add(loopIdx);

                triNodes[j] = nodeId;

                if (!adjacency.ContainsKey(nodeId))
                    adjacency[nodeId] = new HashSet<int>();
            }

            // 同一三角形内的节点互相连接
            for (int a = 0; a < 3; a++)
            {
                for (int b = a + 1; b < 3; b++)
                {
                    if (triNodes[a] >= 0 && triNodes[b] >= 0)
                    {
                        adjacency[triNodes[a]].Add(triNodes[b]);
                        adjacency[triNodes[b]].Add(triNodes[a]);
                    }
                }
            }
        }

        totalUVNodes = nodeIdCounter;
        AddLog($"  UV孤岛: 创建了 {nodeIdCounter} 个UV节点");

        // BFS查找连通分量
        var visited = new HashSet<int>();
        var components = new List<HashSet<int>>();
        componentNodesList = new List<HashSet<int>>();

        foreach (int startNode in adjacency.Keys)
        {
            if (visited.Contains(startNode)) continue;

            var componentNodes = new HashSet<int>();
            var queue = new Queue<int>();
            queue.Enqueue(startNode);

            while (queue.Count > 0)
            {
                int current = queue.Dequeue();
                if (visited.Contains(current)) continue;

                visited.Add(current);
                componentNodes.Add(current);

                if (adjacency.ContainsKey(current))
                {
                    foreach (int neighbor in adjacency[current])
                    {
                        if (!visited.Contains(neighbor))
                            queue.Enqueue(neighbor);
                    }
                }
            }

            if (componentNodes.Count > 0)
            {
                // 将节点转换回顶点索引（去重）
                var componentVerts = new HashSet<int>();
                foreach (int n in componentNodes)
                {
                    if (nodeToVert.ContainsKey(n))
                        componentVerts.Add(nodeToVert[n]);
                }

                components.Add(componentVerts);
                componentNodesList.Add(componentNodes);
            }
        }

        return components;
    }

    /// <summary>
    /// 【新增】在SubMesh内查找连通分量
    /// </summary>
    private List<HashSet<int>> FindConnectedComponentsInSubMesh(int[] triangles, int vertexCount)
    {
        var adjacency = new Dictionary<int, HashSet<int>>();
        
        // 只为三角形中出现的顶点建立邻接关系
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
            
            if (!adjacency.ContainsKey(v0)) adjacency[v0] = new HashSet<int>();
            if (!adjacency.ContainsKey(v1)) adjacency[v1] = new HashSet<int>();
            if (!adjacency.ContainsKey(v2)) adjacency[v2] = new HashSet<int>();
            
            adjacency[v0].Add(v1); adjacency[v0].Add(v2);
            adjacency[v1].Add(v0); adjacency[v1].Add(v2);
            adjacency[v2].Add(v0); adjacency[v2].Add(v1);
        }
        
        var visited = new HashSet<int>();
        var components = new List<HashSet<int>>();
        
        foreach (int startVert in adjacency.Keys)
        {
            if (visited.Contains(startVert)) continue;
            
            var component = new HashSet<int>();
            var queue = new Queue<int>();
            queue.Enqueue(startVert);
            
            while (queue.Count > 0)
            {
                int current = queue.Dequeue();
                if (visited.Contains(current)) continue;
                
                visited.Add(current);
                component.Add(current);
                
                if (adjacency.ContainsKey(current))
                {
                    foreach (int neighbor in adjacency[current])
                    {
                        if (!visited.Contains(neighbor))
                            queue.Enqueue(neighbor);
                    }
                }
            }
            
            if (component.Count > 0)
                components.Add(component);
        }
        
        return components;
    }

    // UV节点映射（用于UV孤岛模式）
    private Dictionary<int, int> loopToNode = new Dictionary<int, int>();
    private Dictionary<int, List<int>> nodeToLoops = new Dictionary<int, List<int>>();
    private Dictionary<int, int> nodeToVert = new Dictionary<int, int>();
    private int totalUVNodes = 0;
    
    /// <summary>
    /// 【新增】为SubMesh建立顶点到三角形的映射
    /// </summary>
    private Dictionary<int, List<int>> BuildVertexToTrianglesMapForSubMesh(int[] triangles)
    {
        var map = new Dictionary<int, List<int>>();
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int triIdx = i / 3;
            for (int j = 0; j < 3; j++)
            {
                int v = triangles[i + j];
                if (!map.ContainsKey(v)) map[v] = new List<int>();
                map[v].Add(triIdx);
            }
        }
        return map;
    }

    /// <summary>
    /// 计算全局UV统计（仅选中的SubMesh）
    /// </summary>
    private void CalculateGlobalUVStats()
    {
        Vector2[] uvs = analyzedMesh.uv;
        
        if (uvs == null || uvs.Length == 0)
        {
            globalMinV = 0f;
            globalMaxV = 1f;
            globalVRange = 1f;
            return;
        }
        
        globalMinV = float.MaxValue;
        globalMaxV = float.MinValue;
        
        // 收集所有选中SubMesh的顶点
        HashSet<int> selectedVertices = new HashSet<int>();
        int[] allTriangles = analyzedMesh.triangles;
        
        for (int subMeshIdx = 0; subMeshIdx < subMeshCount; subMeshIdx++)
        {
            if (!selectedSubMeshes[subMeshIdx]) continue;
            
            var subMeshDesc = analyzedMesh.GetSubMesh(subMeshIdx);
            int indexStart = (int)subMeshDesc.indexStart;
            int indexCount = (int)subMeshDesc.indexCount;
            
            for (int i = 0; i < indexCount; i++)
            {
                selectedVertices.Add(allTriangles[indexStart + i]);
            }
        }
        
        // 计算选中顶点的UV范围
        foreach (int vertIdx in selectedVertices)
        {
            if (vertIdx < uvs.Length)
            {
                float v = uvs[vertIdx].y;
                if (v < globalMinV) globalMinV = v;
                if (v > globalMaxV) globalMaxV = v;
            }
        }
        
        if (globalMinV == float.MaxValue)
        {
            globalMinV = 0f;
            globalMaxV = 1f;
        }
        
        globalVRange = globalMaxV - globalMinV;
        if (globalVRange < 0.001f) globalVRange = 1f;
    }

    private void CalculateWorldYStats()
    {
        if (hairStrips.Count == 0) return;

        Vector3[] vertices = analyzedMesh.vertices;
        Vector2[] uvs = analyzedMesh.uv;
        Transform transform = targetObject.transform;

        AddLog("");
        AddLog("========== 计算世界Y坐标统计 ==========");

        foreach (var strip in hairStrips)
        {
            float sumY = 0f;
            float minY = float.MaxValue;
            float maxY = float.MinValue;

            int rootVertIdx = -1;
            int tipVertIdx = -1;
            float maxV = float.MinValue;
            float minV = float.MaxValue;

            foreach (int vertIdx in strip.vertexIndices)
            {
                Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
                float y = worldPos.y;

                sumY += y;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;

                if (uvs != null && vertIdx < uvs.Length)
                {
                    float v = uvs[vertIdx].y;
                    if (v > maxV)
                    {
                        maxV = v;
                        rootVertIdx = vertIdx;
                    }
                    if (v < minV)
                    {
                        minV = v;
                        tipVertIdx = vertIdx;
                    }
                }
            }

            strip.avgWorldY = sumY / strip.vertexIndices.Count;
            strip.minWorldY = minY;
            strip.maxWorldY = maxY;

            if (rootVertIdx >= 0)
                strip.rootWorldY = transform.TransformPoint(vertices[rootVertIdx]).y;
            if (tipVertIdx >= 0)
                strip.tipWorldY = transform.TransformPoint(vertices[tipVertIdx]).y;
        }

        if (useRootWorldY)
        {
            globalMinWorldY = hairStrips.Min(s => s.rootWorldY);
            globalMaxWorldY = hairStrips.Max(s => s.rootWorldY);
        }
        else
        {
            globalMinWorldY = hairStrips.Min(s => s.avgWorldY);
            globalMaxWorldY = hairStrips.Max(s => s.avgWorldY);
        }

        globalWorldYRange = globalMaxWorldY - globalMinWorldY;
        if (globalWorldYRange < 0.001f) globalWorldYRange = 1f;

        float rootUVMin = hairStrips.Min(s => s.maxV);
        float rootUVMax = hairStrips.Max(s => s.maxV);
        float rootUVRange = rootUVMax - rootUVMin;

        foreach (var strip in hairStrips)
        {
            float referenceY = useRootWorldY ? strip.rootWorldY : strip.avgWorldY;
            float yNormalized = (globalMaxWorldY - referenceY) / globalWorldYRange;
            yNormalized = Mathf.Clamp01(yNormalized);
            strip.worldYOffset = yNormalized * rootUVRange;
        }
    }

    private void ExportDetailedLog()
    {
        string path = EditorUtility.SaveFilePanel("保存详细日志", "",
            $"HairAnalysis_Log_{System.DateTime.Now:yyyyMMdd_HHmmss}", "txt");

        if (string.IsNullOrEmpty(path)) return;

        var sb = new System.Text.StringBuilder();
        sb.AppendLine("========== 毛发分析详细日志 ==========");
        sb.AppendLine($"时间: {System.DateTime.Now}");
        sb.AppendLine($"物体: {targetObject?.name}");
        sb.AppendLine($"Mesh: {analyzedMesh?.name}");
        sb.AppendLine($"Mesh类型: {(isSkinnedMesh ? "SkinnedMeshRenderer" : "MeshFilter")}");
        sb.AppendLine($"SubMesh数量: {subMeshCount}");
        sb.AppendLine();

        sb.AppendLine("---------- 选中的SubMesh ----------");
        for (int i = 0; i < subMeshCount; i++)
        {
            sb.AppendLine($"SubMesh {i}: {(selectedSubMeshes[i] ? "已选" : "未选")}");
        }
        sb.AppendLine();

        sb.AppendLine("---------- 详细日志 ----------");
        foreach (var log in detailedLogs)
        {
            sb.AppendLine(log);
        }

        System.IO.File.WriteAllText(path, sb.ToString());
        Debug.Log($"✓ 详细日志已保存到: {path}");
    }

    private void OnSceneGUI(SceneView sceneView)
    {
        if (!analysisComplete || targetObject == null || hairStrips.Count == 0 || analyzedMesh == null)
            return;

        Vector3[] vertices = analyzedMesh.vertices;
        Vector2[] uvs = analyzedMesh.uv;
        Transform transform = targetObject.transform;

        Handles.matrix = Matrix4x4.identity;

        if (showAllStrips)
        {
            foreach (var strip in hairStrips)
            {
                // 只显示选中SubMesh的Strip
                if (!selectedSubMeshes[strip.subMeshIndex]) continue;
                
                float alpha = strip.index == currentStripIndex ? 1f : 0.2f;
                DrawStrip(strip, vertices, uvs, transform, alpha);
            }
        }
        else if (currentStripIndex < hairStrips.Count)
        {
            DrawStrip(hairStrips[currentStripIndex], vertices, uvs, transform, 1f);
        }
    }

    private void DrawStrip(HairStrip strip, Vector3[] vertices, Vector2[] uvs, Transform transform, float alpha)
    {
        Color stripColor = strip.debugColor;

        Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.3f);
        for (int i = 0; i < strip.triangleIndices.Count; i += 3)
        {
            Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
            Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
            Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
            Handles.DrawAAConvexPolygon(v0, v1, v2);
        }

        Handles.color = new Color(stripColor.r, stripColor.g, stripColor.b, alpha * 0.8f);
        for (int i = 0; i < strip.triangleIndices.Count; i += 3)
        {
            Vector3 v0 = transform.TransformPoint(vertices[strip.triangleIndices[i]]);
            Vector3 v1 = transform.TransformPoint(vertices[strip.triangleIndices[i + 1]]);
            Vector3 v2 = transform.TransformPoint(vertices[strip.triangleIndices[i + 2]]);
            Handles.DrawLine(v0, v1);
            Handles.DrawLine(v1, v2);
            Handles.DrawLine(v2, v0);
        }

        foreach (int vertIdx in strip.vertexIndices)
        {
            Vector3 worldPos = transform.TransformPoint(vertices[vertIdx]);
            float vValue = (uvs != null && vertIdx < uvs.Length) ? uvs[vertIdx].y : 0;

            float finalValue = CalculateFinalBValue(vValue, strip);

            Color vertColor = Color.Lerp(Color.red, Color.green, Mathf.Clamp01(finalValue));
            vertColor.a = alpha;

            Handles.color = vertColor;
            Handles.SphereHandleCap(0, worldPos, Quaternion.identity, vertexSphereSize, EventType.Repaint);

            if ((showVertexLabels || showUVInfo) && alpha > 0.5f)
            {
                string label = "";
                if (showVertexLabels) label += $"[{vertIdx}]";
                if (showUVInfo)
                {
                    label += $" V:{vValue:F3}";
                    if (enableWorldYCorrection)
                    {
                        label += $" B:{finalValue:F2}";
                    }
                }
                Handles.Label(worldPos + Vector3.up * vertexSphereSize * 1.5f, label, EditorStyles.miniLabel);
            }
        }

        if (showRootTipMarkers && alpha > 0.5f)
        {
            float rootFinal = CalculateFinalBValue(strip.maxV, strip);
            float tipFinal = CalculateFinalBValue(strip.minV, strip);

            Handles.color = Color.green;
            Handles.SphereHandleCap(0, strip.rootPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);

            string rootLabel = $"ROOT\nV={strip.maxV:F3}\nB={rootFinal:F3}";
            Handles.Label(strip.rootPosition + Vector3.up * vertexSphereSize * 3f, rootLabel, EditorStyles.whiteBoldLabel);

            Handles.color = Color.red;
            Handles.SphereHandleCap(0, strip.tipPosition, Quaternion.identity, vertexSphereSize * 2.5f, EventType.Repaint);

            string tipLabel = $"TIP\nV={strip.minV:F3}\nB={tipFinal:F3}";
            Handles.Label(strip.tipPosition + Vector3.up * vertexSphereSize * 3f, tipLabel, EditorStyles.whiteBoldLabel);

            Handles.color = Color.yellow;
            Handles.DrawDottedLine(strip.rootPosition, strip.tipPosition, 3f);
        }
    }

    private void FocusOnStrip(int index)
    {
        if (index >= hairStrips.Count) return;

        var strip = hairStrips[index];
        Vector3 center = (strip.rootPosition + strip.tipPosition) / 2f;
        float size = Mathf.Max(Vector3.Distance(strip.rootPosition, strip.tipPosition) * 3f, 0.1f);

        SceneView.lastActiveSceneView?.LookAt(center, SceneView.lastActiveSceneView.rotation, size);
        SceneView.RepaintAll();
    }

    /// <summary>
    /// 【重写】生成带UV差值的Mesh - 保留未选SubMesh
    /// </summary>
    private void GenerateMeshWithUVDifference()
    {
        // 创建新Mesh，复制所有原始数据
        Mesh newMesh = new Mesh();
        newMesh.name = originalMesh.name + $"_UVDiff_{uvDifferenceMode}";
        if (enableWorldYCorrection)
        {
            newMesh.name += $"_YCorr_{worldYCorrectionMode}";
        }

        // 复制基础数据
        newMesh.vertices = originalMesh.vertices;
        newMesh.normals = originalMesh.normals;
        newMesh.tangents = originalMesh.tangents;
        newMesh.uv = originalMesh.uv;
        newMesh.uv2 = originalMesh.uv2;
        newMesh.uv3 = originalMesh.uv3;
        newMesh.uv4 = originalMesh.uv4;
        
        // 复制骨骼相关数据（如果是SkinnedMesh）
        if (isSkinnedMesh)
        {
            newMesh.bindposes = originalMesh.bindposes;
            newMesh.boneWeights = originalMesh.boneWeights;
        }

        // 复制所有SubMesh
        newMesh.subMeshCount = originalMesh.subMeshCount;
        for (int i = 0; i < originalMesh.subMeshCount; i++)
        {
            var desc = originalMesh.GetSubMesh(i);
            int[] subMeshTriangles = new int[desc.indexCount];
            int[] allTriangles = originalMesh.triangles;
            System.Array.Copy(allTriangles, desc.indexStart, subMeshTriangles, 0, desc.indexCount);
            newMesh.SetTriangles(subMeshTriangles, i);
        }

        // 处理顶点颜色
        Vector2[] uvs = newMesh.uv;
        Color[] colors = originalMesh.colors;
        
        // 如果原始Mesh没有顶点颜色，创建默认颜色
        if (colors == null || colors.Length != newMesh.vertexCount)
        {
            colors = new Color[newMesh.vertexCount];
            for (int i = 0; i < colors.Length; i++)
                colors[i] = new Color(1, 1, 0, 1); // 默认黄色
        }

        // 创建顶点到毛发片的映射
        Dictionary<int, HairStrip> vertexToStrip = new Dictionary<int, HairStrip>();
        foreach (var strip in hairStrips)
        {
            // 只处理选中SubMesh的Strip
            if (!selectedSubMeshes[strip.subMeshIndex]) continue;
            
            foreach (int vertIdx in strip.vertexIndices)
            {
                if (!vertexToStrip.ContainsKey(vertIdx))
                {
                    vertexToStrip[vertIdx] = strip;
                }
            }
        }

        // 计算每个顶点的最终B值
        int modifiedCount = 0;
        for (int i = 0; i < colors.Length; i++)
        {
            if (vertexToStrip.ContainsKey(i))
            {
                HairStrip strip = vertexToStrip[i];
                float v = uvs[i].y;
                float finalB = CalculateFinalBValue(v, strip);
                colors[i].b = finalB * 0.5f + 0.5f;
                modifiedCount++;
            }
            // 未分配的顶点保持原始颜色
        }

        newMesh.colors = colors;
        newMesh.RecalculateBounds();

        // 应用并保存
        string path = EditorUtility.SaveFilePanelInProject(
            "保存处理后的Mesh", newMesh.name, "asset", "选择保存位置");

        if (!string.IsNullOrEmpty(path))
        {
            AssetDatabase.CreateAsset(newMesh, path);
            AssetDatabase.SaveAssets();
            
            Debug.Log($"✓ Mesh已保存: {path}");
            Debug.Log($"  修改了 {modifiedCount}/{newMesh.vertexCount} 个顶点的颜色");
            Debug.Log($"  处理了 {selectedSubMeshes.Count(s => s)}/{subMeshCount} 个SubMesh");
            Debug.Log($"  UV差值模式: {uvDifferenceMode}");
            if (enableWorldYCorrection)
            {
                Debug.Log($"  世界Y修正: {worldYCorrectionMode}, 权重: {worldYCorrectionWeight}");
            }
            
            // 询问是否应用到当前物体
            if (EditorUtility.DisplayDialog("应用Mesh?", 
                "是否将新Mesh应用到当前物体？\n（原始Mesh不会被修改）", "应用", "取消"))
            {
                ApplyMesh(newMesh);
            }
        }
    }

    private void ExportSingleStrip(HairStrip strip)
    {
        if (strip == null || strip.vertexIndices == null || strip.vertexIndices.Count < 2)
        {
            EditorUtility.DisplayDialog("错误", "毛发片数据无效", "确定");
            return;
        }

        try
        {
            Mesh mesh = CreateMeshFromStrip(strip);

            if (mesh == null || mesh.vertexCount == 0)
            {
                EditorUtility.DisplayDialog("错误", "生成Mesh失败", "确定");
                return;
            }

            string meshName = $"HairStrip_{strip.index}_SubMesh{strip.subMeshIndex}_{uvDifferenceMode}";
            if (enableWorldYCorrection)
            {
                meshName += $"_YCorr";
            }

            string path = EditorUtility.SaveFilePanelInProject(
                "保存毛发片", meshName, "asset", "选择保存位置");

            if (!string.IsNullOrEmpty(path))
            {
                AssetDatabase.CreateAsset(mesh, path);
                AssetDatabase.SaveAssets();
                Debug.Log($"✓ 毛发片 #{strip.index} (SubMesh {strip.subMeshIndex}) 已导出到: {path}");
            }
        }
        catch (System.Exception e)
        {
            EditorUtility.DisplayDialog("导出失败", $"错误: {e.Message}", "确定");
        }
    }

    private void ExportAllStrips()
    {
        string folder = EditorUtility.SaveFolderPanel("选择导出文件夹", "Assets", "HairStrips");
        if (string.IsNullOrEmpty(folder)) return;

        if (folder.StartsWith(Application.dataPath))
        {
            folder = "Assets" + folder.Substring(Application.dataPath.Length);
        }

        int successCount = 0;
        int failCount = 0;

        try
        {
            for (int i = 0; i < hairStrips.Count; i++)
            {
                var strip = hairStrips[i];

                bool cancel = EditorUtility.DisplayCancelableProgressBar(
                    "导出毛发片",
                    $"正在导出 {i + 1}/{hairStrips.Count}",
                    (float)i / hairStrips.Count);

                if (cancel) break;

                try
                {
                    Mesh mesh = CreateMeshFromStrip(strip);

                    if (mesh != null && mesh.vertexCount > 0)
                    {
                        string path = $"{folder}/HairStrip_{strip.index}_SM{strip.subMeshIndex}.asset";
                        AssetDatabase.CreateAsset(mesh, path);
                        successCount++;
                    }
                    else
                    {
                        failCount++;
                    }
                }
                catch
                {
                    failCount++;
                }
            }
        }
        finally
        {
            EditorUtility.ClearProgressBar();
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        EditorUtility.DisplayDialog("导出结果",
            $"导出完成！\n成功: {successCount}\n失败: {failCount}", "确定");
    }

    private void ExportAnalysisReport()
    {
        string path = EditorUtility.SaveFilePanel("保存分析报告", "", "HairAnalysisReport", "txt");
        if (string.IsNullOrEmpty(path)) return;

        var sb = new System.Text.StringBuilder();
        sb.AppendLine("========== 毛发分析报告 ==========");
        sb.AppendLine($"物体: {targetObject.name}");
        sb.AppendLine($"Mesh: {analyzedMesh.name}");
        sb.AppendLine($"Mesh类型: {(isSkinnedMesh ? "SkinnedMeshRenderer" : "MeshFilter")}");
        sb.AppendLine($"总顶点数: {analyzedMesh.vertexCount}");
        sb.AppendLine($"总三角形数: {analyzedMesh.triangles.Length / 3}");
        sb.AppendLine($"SubMesh数量: {subMeshCount}");
        sb.AppendLine($"识别毛发片数: {hairStrips.Count}");
        sb.AppendLine();

        sb.AppendLine("---------- SubMesh选择 ----------");
        for (int i = 0; i < subMeshCount; i++)
        {
            var desc = analyzedMesh.GetSubMesh(i);
            sb.AppendLine($"SubMesh {i}: {(selectedSubMeshes[i] ? "已选" : "未选")} ({desc.indexCount / 3} 三角形)");
            
            if (subMeshToStrips.ContainsKey(i))
            {
                sb.AppendLine($"  识别到 {subMeshToStrips[i].Count} 个毛发片");
            }
        }
        sb.AppendLine();

        sb.AppendLine("---------- 全局统计 ----------");
        sb.AppendLine($"UV V值范围: {globalMinV:F4} ~ {globalMaxV:F4} (Range={globalVRange:F4})");

        if (enableWorldYCorrection)
        {
            sb.AppendLine($"世界Y范围: {globalMinWorldY:F4} ~ {globalMaxWorldY:F4} (Range={globalWorldYRange:F4})");
        }
        sb.AppendLine();

        sb.AppendLine("---------- 各毛发片详情 ----------");

        foreach (var strip in hairStrips)
        {
            float rootDiff = CalculateUVDifference(strip.maxV, strip);
            float tipDiff = CalculateUVDifference(strip.minV, strip);
            float rootFinal = CalculateFinalBValue(strip.maxV, strip);
            float tipFinal = CalculateFinalBValue(strip.minV, strip);

            sb.AppendLine($"\n毛发片 #{strip.index} (SubMesh {strip.subMeshIndex}):");
            sb.AppendLine($"  顶点数: {strip.vertexCount}");
            sb.AppendLine($"  三角形数: {strip.triangleCount}");
            sb.AppendLine($"  V值范围: {strip.minV:F4} ~ {strip.maxV:F4} (跨度:{strip.vRange:F4})");
            sb.AppendLine($"  UV差值: 根部={rootDiff:F4}, 尖端={tipDiff:F4}");

            if (enableWorldYCorrection)
            {
                sb.AppendLine($"  世界Y: 根部={strip.rootWorldY:F4}, 尖端={strip.tipWorldY:F4}");
                sb.AppendLine($"  Y偏移: {strip.worldYOffset:F4}");
                sb.AppendLine($"  最终B值: 根部={rootFinal:F4}, 尖端={tipFinal:F4}");
            }
        }

        System.IO.File.WriteAllText(path, sb.ToString());
        Debug.Log($"✓ 报告已保存: {path}");
    }

    private Mesh CreateMeshFromStrip(HairStrip strip)
    {
        Vector3[] origVerts = analyzedMesh.vertices;
        Vector2[] origUVs = analyzedMesh.uv;
        Vector3[] origNormals = analyzedMesh.normals;
        Color[] origColors = analyzedMesh.colors;
        BoneWeight[] origBoneWeights = isSkinnedMesh ? analyzedMesh.boneWeights : null;

        HashSet<int> allVertices = new HashSet<int>(strip.vertexIndices);
        for (int i = 0; i < strip.triangleIndices.Count; i++)
        {
            allVertices.Add(strip.triangleIndices[i]);
        }

        List<int> finalVertexList = allVertices.ToList();
        Dictionary<int, int> remap = new Dictionary<int, int>();
        for (int i = 0; i < finalVertexList.Count; i++)
        {
            remap[finalVertexList[i]] = i;
        }

        int vertCount = finalVertexList.Count;
        Vector3[] newVerts = new Vector3[vertCount];
        Vector2[] newUVs = new Vector2[vertCount];
        Vector3[] newNormals = new Vector3[vertCount];
        Color[] newColors = new Color[vertCount];
        BoneWeight[] newBoneWeights = isSkinnedMesh ? new BoneWeight[vertCount] : null;

        for (int i = 0; i < vertCount; i++)
        {
            int origIdx = finalVertexList[i];

            newVerts[i] = origVerts[origIdx];
            newUVs[i] = (origUVs != null && origIdx < origUVs.Length) ? origUVs[origIdx] : Vector2.zero;
            newNormals[i] = (origNormals != null && origIdx < origNormals.Length) ? origNormals[origIdx] : Vector3.up;
            newColors[i] = (origColors != null && origIdx < origColors.Length) ? origColors[origIdx] : Color.white;
            
            if (isSkinnedMesh && origBoneWeights != null && origIdx < origBoneWeights.Length)
            {
                newBoneWeights[i] = origBoneWeights[origIdx];
            }
        }

        List<int> newTriangles = new List<int>();
        for (int i = 0; i < strip.triangleIndices.Count; i += 3)
        {
            if (i + 2 < strip.triangleIndices.Count)
            {
                int idx0 = strip.triangleIndices[i];
                int idx1 = strip.triangleIndices[i + 1];
                int idx2 = strip.triangleIndices[i + 2];

                if (remap.ContainsKey(idx0) && remap.ContainsKey(idx1) && remap.ContainsKey(idx2))
                {
                    newTriangles.Add(remap[idx0]);
                    newTriangles.Add(remap[idx1]);
                    newTriangles.Add(remap[idx2]);
                }
            }
        }

        for (int i = 0; i < vertCount; i++)
        {
            float v = newUVs[i].y;
            float finalB = CalculateFinalBValue(v, strip);
            newColors[i].b = finalB * 0.5f + 0.5f;
        }

        Mesh mesh = new Mesh();
        mesh.name = $"HairStrip_{strip.index}_SM{strip.subMeshIndex}";
        mesh.vertices = newVerts;
        mesh.uv = newUVs;
        mesh.normals = newNormals;
        mesh.colors = newColors;

        if (isSkinnedMesh && newBoneWeights != null)
        {
            mesh.boneWeights = newBoneWeights;
            mesh.bindposes = analyzedMesh.bindposes;
        }

        if (newTriangles.Count >= 3)
        {
            mesh.triangles = newTriangles.ToArray();
        }

        mesh.RecalculateBounds();
        return mesh;
    }

    #region Helper Methods

    private Mesh GetMesh()
    {
        if (targetObject == null) return null;
        
        if (skinnedMeshRenderer != null)
            return skinnedMeshRenderer.sharedMesh;
        if (meshFilter != null)
            return meshFilter.sharedMesh;
            
        return null;
    }

    private void ApplyMesh(Mesh mesh)
    {
        if (skinnedMeshRenderer != null)
        {
            skinnedMeshRenderer.sharedMesh = mesh;
        }
        else if (meshFilter != null)
        {
            meshFilter.sharedMesh = mesh;
        }
    }

    #endregion
}