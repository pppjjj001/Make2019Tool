// CubemapGenerator.cs
// 放置路径: Assets/Scripts/TextureGeneration/CubemapGenerator.cs

using UnityEngine;
using UnityEngine.Rendering;
using System.IO;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace EnvironmentTextureBaker
{
    /// <summary>
    /// Cubemap生成器 - 从场景捕获环境生成Cubemap贴图
    /// </summary>
    public class CubemapGenerator : MonoBehaviour
    {
        #region 设置
        
        [Header("捕获设置")]
        [Tooltip("Cubemap分辨率")]
        public CubemapResolution resolution = CubemapResolution._512;
        
        [Tooltip("是否使用HDR")]
        public bool useHDR = true;
        
        [Tooltip("渲染的层级")]
        public LayerMask cullingMask = -1;
        
        [Tooltip("近裁剪面")]
        public float nearClipPlane = 0.1f;
        
        [Tooltip("远裁剪面")]
        public float farClipPlane = 1000f;
        
        [Header("清除设置")]
        public CameraClearFlags clearFlags = CameraClearFlags.Skybox;
        public Color backgroundColor = Color.black;
        
        [Header("输出设置")]
        public string outputFolder = "Assets/GeneratedTextures/Cubemaps";
        public string outputFileName = "EnvironmentCubemap";
        public CubemapOutputFormat outputFormat = CubemapOutputFormat.EXR;
        
        #endregion
        
        #region 枚举
        
        public enum CubemapResolution
        {
            _64 = 64,
            _128 = 128,
            _256 = 256,
            _512 = 512,
            _1024 = 1024,
            _2048 = 2048,
            _4096 = 4096
        }
        
        public enum CubemapOutputFormat
        {
            EXR,
            PNG,
            Asset
        }
        
        #endregion
        
        #region 公共方法
        
        /// <summary>
        /// 在当前位置生成Cubemap
        /// </summary>
        public Cubemap GenerateCubemap()
        {
            return GenerateCubemapAtPosition(transform.position);
        }
        
        /// <summary>
        /// 在指定位置生成Cubemap
        /// </summary>
        public Cubemap GenerateCubemapAtPosition(Vector3 position)
        {
            int res = (int)resolution;
            
            // 创建Cubemap
            TextureFormat format = useHDR ? TextureFormat.RGBAHalf : TextureFormat.RGBA32;
            Cubemap cubemap = new Cubemap(res, format, true);
            cubemap.name = outputFileName;
            
            // 创建临时相机
            GameObject camGO = new GameObject("CubemapCaptureCamera");
            Camera cam = camGO.AddComponent<Camera>();
            camGO.transform.position = position;
            
            // 配置相机
            cam.cullingMask = cullingMask;
            cam.nearClipPlane = nearClipPlane;
            cam.farClipPlane = farClipPlane;
            cam.clearFlags = clearFlags;
            cam.backgroundColor = backgroundColor;
            cam.allowHDR = useHDR;
            
            // 渲染Cubemap
            cam.RenderToCubemap(cubemap);
            
            // 应用更改
            cubemap.Apply();
            
            // 清理
            DestroyImmediate(camGO);
            
            Debug.Log($"Cubemap generated at position {position} with resolution {res}x{res}");
            
            return cubemap;
        }
        
        /// <summary>
        /// 生成并保存Cubemap
        /// </summary>
        public Cubemap GenerateAndSaveCubemap()
        {
            Cubemap cubemap = GenerateCubemap();
            
            #if UNITY_EDITOR
            SaveCubemap(cubemap);
            #endif
            
            return cubemap;
        }
        
        #if UNITY_EDITOR
        /// <summary>
        /// 保存Cubemap到文件
        /// </summary>
        public void SaveCubemap(Cubemap cubemap)
        {
            if (cubemap == null)
            {
                Debug.LogError("Cubemap is null, cannot save.");
                return;
            }
            
            // 确保目录存在
            if (!Directory.Exists(outputFolder))
            {
                Directory.CreateDirectory(outputFolder);
            }
            
            string fullPath =string.Empty;
            
            switch (outputFormat)
            {
                case CubemapOutputFormat.Asset:
                    fullPath = $"{outputFolder}/{outputFileName}.cubemap";
                    SaveCubemapAsAsset(cubemap, fullPath);
                    break;
                    
                case CubemapOutputFormat.EXR:
                    fullPath = $"{outputFolder}/{outputFileName}.exr";
                    SaveCubemapAsEXR(cubemap, fullPath);
                    break;
                    
                case CubemapOutputFormat.PNG:
                    fullPath = $"{outputFolder}/{outputFileName}.png";
                    SaveCubemapAsPNG(cubemap, fullPath);
                    break;
            }
            
            AssetDatabase.Refresh();
            Debug.Log($"Cubemap saved to {fullPath}");
        }
        
        private void SaveCubemapAsAsset(Cubemap cubemap, string path)
        {
            // 创建副本以保存
            Cubemap saveCubemap = new Cubemap(cubemap.width, cubemap.format, cubemap.mipmapCount > 1);
            
            // 复制每个面
            CubemapFace[] faces = new CubemapFace[]
            {
                CubemapFace.PositiveX, CubemapFace.NegativeX,
                CubemapFace.PositiveY, CubemapFace.NegativeY,
                CubemapFace.PositiveZ, CubemapFace.NegativeZ
            };
            
            foreach (var face in faces)
            {
                Color[] pixels = cubemap.GetPixels(face);
                saveCubemap.SetPixels(pixels, face);
            }
            saveCubemap.Apply();
            
            AssetDatabase.CreateAsset(saveCubemap, path);
            AssetDatabase.SaveAssets();
        }
        
        private void SaveCubemapAsEXR(Cubemap cubemap, string path)
        {
            // 将Cubemap展开为水平十字形或垂直条带
            int faceSize = cubemap.width;
            int width = faceSize * 4;  // 水平条带: 6个面
            int height = faceSize * 3;
            
            Texture2D outputTex = new Texture2D(width, height, TextureFormat.RGBAHalf, false);
            
            // 填充背景
            Color[] clearColors = new Color[width * height];
            for (int i = 0; i < clearColors.Length; i++)
                clearColors[i] = Color.clear;
            outputTex.SetPixels(clearColors);
            
            // 十字形布局:
            //        +Y
            //   -X   +Z   +X   -Z
            //        -Y
            
            CopyFaceToTexture(cubemap, CubemapFace.PositiveY, outputTex, faceSize, faceSize * 2);     // 上
            CopyFaceToTexture(cubemap, CubemapFace.NegativeX, outputTex, 0, faceSize);               // 左
            CopyFaceToTexture(cubemap, CubemapFace.PositiveZ, outputTex, faceSize, faceSize);        // 前
            CopyFaceToTexture(cubemap, CubemapFace.PositiveX, outputTex, faceSize * 2, faceSize);    // 右
            CopyFaceToTexture(cubemap, CubemapFace.NegativeZ, outputTex, faceSize * 3, faceSize);    // 后
            CopyFaceToTexture(cubemap, CubemapFace.NegativeY, outputTex, faceSize, 0);              // 下
            
            outputTex.Apply();
            
            byte[] bytes = outputTex.EncodeToEXR(Texture2D.EXRFlags.CompressZIP);
            File.WriteAllBytes(path, bytes);
            
            DestroyImmediate(outputTex);
        }
        
        private void SaveCubemapAsPNG(Cubemap cubemap, string path)
        {
            int faceSize = cubemap.width;
            int width = faceSize * 4;
            int height = faceSize * 3;
            
            Texture2D outputTex = new Texture2D(width, height, TextureFormat.RGBA32, false);
            
            Color[] clearColors = new Color[width * height];
            for (int i = 0; i < clearColors.Length; i++)
                clearColors[i] = Color.clear;
            outputTex.SetPixels(clearColors);
            
            CopyFaceToTexture(cubemap, CubemapFace.PositiveY, outputTex, faceSize, faceSize * 2);
            CopyFaceToTexture(cubemap, CubemapFace.NegativeX, outputTex, 0, faceSize);
            CopyFaceToTexture(cubemap, CubemapFace.PositiveZ, outputTex, faceSize, faceSize);
            CopyFaceToTexture(cubemap, CubemapFace.PositiveX, outputTex, faceSize * 2, faceSize);
            CopyFaceToTexture(cubemap, CubemapFace.NegativeZ, outputTex, faceSize * 3, faceSize);
            CopyFaceToTexture(cubemap, CubemapFace.NegativeY, outputTex, faceSize, 0);
            
            outputTex.Apply();
            
            byte[] bytes = outputTex.EncodeToPNG();
            File.WriteAllBytes(path, bytes);
            
            DestroyImmediate(outputTex);
        }
        
        private void CopyFaceToTexture(Cubemap cubemap, CubemapFace face, Texture2D target, int offsetX, int offsetY)
        {
            Color[] facePixels = cubemap.GetPixels(face);
            int faceSize = cubemap.width;
            
            for (int y = 0; y < faceSize; y++)
            {
                for (int x = 0; x < faceSize; x++)
                {
                    // Cubemap的Y轴是翻转的
                    Color pixel = facePixels[x + (faceSize - 1 - y) * faceSize];
                    target.SetPixel(offsetX + x, offsetY + y, pixel);
                }
            }
        }
        #endif
        
        #endregion
        
        #region 编辑器可视化
        
        #if UNITY_EDITOR
        private void OnDrawGizmosSelected()
        {
            Gizmos.color = Color.cyan;
            Gizmos.DrawWireSphere(transform.position, 0.5f);
            
            // 绘制6个方向
            float arrowLength = 1f;
            Vector3[] directions = new Vector3[]
            {
                Vector3.right, Vector3.left,
                Vector3.up, Vector3.down,
                Vector3.forward, Vector3.back
            };
            
            Color[] colors = new Color[]
            {
                Color.red, new Color(0.5f, 0, 0),
                Color.green, new Color(0, 0.5f, 0),
                Color.blue, new Color(0, 0, 0.5f)
            };
            
            for (int i = 0; i < 6; i++)
            {
                Gizmos.color = colors[i];
                Gizmos.DrawRay(transform.position, directions[i] * arrowLength);
            }
        }
        #endif
        
        #endregion
    }
}