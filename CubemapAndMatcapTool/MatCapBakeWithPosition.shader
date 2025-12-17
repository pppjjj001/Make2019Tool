// MatCapBakeWithPosition.shader
// 放置路径: Assets/Shaders/Hidden/MatCapBakeWithPosition.shader

Shader "Hidden/MatCapBakeWithPosition"
{
    Properties
    {
        _EnvironmentCubemap ("Environment Cubemap", Cube) = "" {}
        _EnvironmentIntensity ("Environment Intensity", Float) = 1.0
        _CubemapMipLevel ("Cubemap Mip Level", Float) = 0.0
        
        _SampleWorldPosition ("Sample World Position", Vector) = (0, 0, 0, 0)
        _CubemapCapturePosition ("Cubemap Capture Position", Vector) = (0, 0, 0, 0)
        _UseBoxProjection ("Use Box Projection", Float) = 0.0
        _BoxProjectionMin ("Box Projection Min", Vector) = (-10, -10, -10, 0)
        _BoxProjectionMax ("Box Projection Max", Vector) = (10, 10, 10, 0)
        
        _BaseColor ("Base Color", Color) = (1, 1, 1, 1)
        _Metallic ("Metallic", Range(0, 1)) = 0.5
        _Smoothness ("Smoothness", Range(0, 1)) = 0.8
        _IncludeDiffuse ("Include Diffuse", Float) = 1.0
        _IncludeSpecular ("Include Specular", Float) = 1.0
        
        _UseFresnelMask ("Use Fresnel Mask", Float) = 1.0
        _FresnelPower ("Fresnel Power", Float) = 3.0
        _FresnelScale ("Fresnel Scale", Float) = 1.0
        _FresnelBias ("Fresnel Bias", Float) = 0.0
        _CenterMaskPower ("Center Mask Power", Float) = 2.0
        _EdgeThreshold ("Edge Threshold", Float) = 0.3
        _EdgeSoftness ("Edge Softness", Float) = 0.2
        _CenterColor ("Center Color", Color) = (0, 0, 0, 1)
    }
    
    SubShader
    {
        Tags 
        { 
            "RenderType" = "Opaque" 
            "RenderPipeline" = "UniversalPipeline"
            "Queue" = "Geometry"
        }
        
        Pass
        {
            Name "MatCapBakeWithPosition"
            Tags { "LightMode" = "UniversalForward" }
            
            Cull Back
            ZWrite On
            ZTest LEqual
            
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            
            // Unity 2019 URP
            #pragma prefer_hlslcc gles
            #pragma exclude_renderers d3d11_9x
            
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            
            // ================================================================
            //                          CBUFFER
            // ================================================================
            
            TEXTURECUBE(_EnvironmentCubemap);
            SAMPLER(sampler_EnvironmentCubemap);
            
            CBUFFER_START(UnityPerMaterial)
                float _EnvironmentIntensity;
                float _CubemapMipLevel;
                
                float4 _SampleWorldPosition;
                float4 _CubemapCapturePosition;
                float _UseBoxProjection;
                float4 _BoxProjectionMin;
                float4 _BoxProjectionMax;
                
                float4 _BaseColor;
                float _Metallic;
                float _Smoothness;
                float _IncludeDiffuse;
                float _IncludeSpecular;
                
                float _UseFresnelMask;
                float _FresnelPower;
                float _FresnelScale;
                float _FresnelBias;
                float _CenterMaskPower;
                float _EdgeThreshold;
                float _EdgeSoftness;
                float4 _CenterColor;
            CBUFFER_END
            
            // ================================================================
            //                          结构体
            // ================================================================
            
            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
            };
            
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS : TEXCOORD0;
                float3 positionOS : TEXCOORD1;  // 用于计算球面位置
            };
            
            // ================================================================
            //                      Cubemap采样函数
            // ================================================================
            
            // 盒投影校正
            float3 BoxProjection(float3 direction, float3 position, 
                                 float3 cubemapPosition, float3 boxMin, float3 boxMax)
            {
                float3 factors = ((direction > 0 ? boxMax : boxMin) - position) / direction;
                float scalar = min(min(factors.x, factors.y), factors.z);
                float3 intersectPos = position + direction * scalar;
                return intersectPos - cubemapPosition;
            }
            
            // 采样Cubemap（带位置校正）
            float3 SampleCubemapWithPosition(float3 direction, float3 worldPosition, float mipLevel)
            {
                float3 sampleDir = direction;
                
                if (_UseBoxProjection > 0.5)
                {
                    sampleDir = BoxProjection(
                        direction,
                        worldPosition,
                        _CubemapCapturePosition.xyz,
                        _BoxProjectionMin.xyz,
                        _BoxProjectionMax.xyz
                    );
                }
                
                return SAMPLE_TEXTURECUBE_LOD(_EnvironmentCubemap, sampler_EnvironmentCubemap, 
                                              sampleDir, mipLevel).rgb;
            }
            
            // 采样环境漫反射
            float3 SampleEnvironmentDiffuse(float3 normal, float3 worldPosition)
            {
                float diffuseMip = max(_CubemapMipLevel, 5.0);
                return SampleCubemapWithPosition(normal, worldPosition, diffuseMip);
            }
            
            // 采样环境高光反射
            float3 SampleEnvironmentSpecular(float3 reflectDir, float3 worldPosition, float roughness)
            {
                float mipLevel = roughness * 7.0 + _CubemapMipLevel;
                return SampleCubemapWithPosition(reflectDir, worldPosition, mipLevel);
            }
            
            // ================================================================
            //                          PBR函数
            // ================================================================
            
            float3 FresnelSchlick(float cosTheta, float3 F0)
            {
                return F0 + (1.0 - F0) * pow(saturate(1.0 - cosTheta), 5.0);
            }
            
            float3 FresnelSchlickRoughness(float cosTheta, float3 F0, float roughness)
            {
                float3 oneMinusRoughness = 1.0 - roughness;
                return F0 + (max(oneMinusRoughness, F0) - F0) * pow(saturate(1.0 - cosTheta), 5.0);
            }
            
            // 计算PBR环境光照
            float3 CalculatePBREnvironment(float3 normal, float3 viewDir, float3 worldPosition,
                                           float3 albedo, float metallic, float smoothness)
            {
                float roughness = 1.0 - smoothness;
                float3 reflectDir = reflect(-viewDir, normal);
                float NdotV = saturate(dot(normal, viewDir));
                
                // F0
                float3 F0 = lerp(0.04, albedo, metallic);
                
                // 菲涅尔
                float3 F = FresnelSchlickRoughness(NdotV, F0, roughness);
                
                // 能量守恒
                float3 kS = F;
                float3 kD = (1.0 - kS) * (1.0 - metallic);
                
                float3 result = 0;
                
                // 漫反射
                if (_IncludeDiffuse > 0.5)
                {
                    float3 irradiance = SampleEnvironmentDiffuse(normal, worldPosition);
                    float3 diffuse = irradiance * albedo;
                    result += kD * diffuse;
                }
                
                // 高光反射
                if (_IncludeSpecular > 0.5)
                {
                    float3 prefilteredColor = SampleEnvironmentSpecular(reflectDir, worldPosition, roughness);
                    
                    // 简化的环境BRDF
                    float2 envBRDF = float2(
                        saturate(1.0 - roughness + (1.0 - NdotV) * 0.5),
                        roughness * (1.0 - NdotV) * 0.3
                    );
                    float3 specular = prefilteredColor * (F * envBRDF.x + envBRDF.y);
                    result += specular;
                }
                
                return result * _EnvironmentIntensity;
            }
            
            // ================================================================
            //                          菲涅尔边缘遮罩
            // ================================================================
            
            float CalculateFresnelMask(float NdotV)
            {
                if (_UseFresnelMask < 0.5)
                    return 1.0;
                
                // 基础菲涅尔
                float fresnel = pow(1.0 - NdotV, _FresnelPower) * _FresnelScale + _FresnelBias;
                
                // 中心遮罩
                float centerMask = pow(NdotV, _CenterMaskPower);
                
                // 边缘阈值
                float edgeFactor = 1.0 - NdotV;
                float edgeMask = smoothstep(_EdgeThreshold - _EdgeSoftness, 
                                            _EdgeThreshold + _EdgeSoftness, 
                                            edgeFactor);
                
                // 组合
                float finalMask = saturate(fresnel * edgeMask * (1.0 - centerMask * 0.5));
                
                return finalMask;
            }
            
            // ================================================================
            //                          顶点着色器
            // ================================================================
            
            Varyings vert(Attributes input)
            {
                Varyings output;
                
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.positionOS = input.positionOS.xyz;
                
                return output;
            }
            
            // ================================================================
            //                          片元着色器
            // ================================================================
            
            half4 frag(Varyings input) : SV_Target
            {
                // 法线（球体的法线就是归一化的位置）
                float3 normalWS = normalize(input.normalWS);
                
                // 计算世界位置：采样位置 + 球体表面偏移
                // 球体半径0.5，缩放2倍后半径1
                float3 surfaceOffset = normalWS * 1.0;
                float3 worldPosition = _SampleWorldPosition.xyz + surfaceOffset;
                
                // 视线方向 - 正交相机从Z负方向看
                float3 viewDirWS = float3(0, 0, 1);
                
                // NdotV
                float NdotV = saturate(dot(normalWS, viewDirWS));
                
                // PBR环境光照
                float3 pbrColor = CalculatePBREnvironment(
                    normalWS, 
                    viewDirWS, 
                    worldPosition,
                    _BaseColor.rgb, 
                    _Metallic, 
                    _Smoothness
                );
                
                // 菲涅尔边缘遮罩
                float fresnelMask = CalculateFresnelMask(NdotV);
                
                // 混合
                float3 finalColor = lerp(_CenterColor.rgb, pbrColor, fresnelMask);
                
                // Alpha
                float alpha = lerp(_CenterColor.a, 1.0, fresnelMask);
                
                return half4(finalColor, alpha);
            }
            
            ENDHLSL
        }
    }
    
    // 备用Pass：不使用URP时
    SubShader
    {
        Tags { "RenderType" = "Opaque" }
        
        Pass
        {
            Name "MatCapBakeFallback"
            
            Cull Back
            ZWrite On
            
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            
            #include "UnityCG.cginc"
            
            samplerCUBE _EnvironmentCubemap;
            
            float _EnvironmentIntensity;
            float _CubemapMipLevel;
            
            float4 _SampleWorldPosition;
            float4 _CubemapCapturePosition;
            float _UseBoxProjection;
            float4 _BoxProjectionMin;
            float4 _BoxProjectionMax;
            
            float4 _BaseColor;
            float _Metallic;
            float _Smoothness;
            float _IncludeDiffuse;
            float _IncludeSpecular;
            
            float _UseFresnelMask;
            float _FresnelPower;
            float _FresnelScale;
            float _FresnelBias;
            float _CenterMaskPower;
            float _EdgeThreshold;
            float _EdgeSoftness;
            float4 _CenterColor;
            
            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
            };
            
            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 normalWS : TEXCOORD0;
            };
            
            // 盒投影
            float3 BoxProjection(float3 direction, float3 position, 
                                 float3 cubemapPosition, float3 boxMin, float3 boxMax)
            {
                float3 factors = ((direction > 0 ? boxMax : boxMin) - position) / direction;
                float scalar = min(min(factors.x, factors.y), factors.z);
                float3 intersectPos = position + direction * scalar;
                return intersectPos - cubemapPosition;
            }
            
            float3 SampleCubemapWithPosition(float3 direction, float3 worldPosition, float mipLevel)
            {
                float3 sampleDir = direction;
                
                if (_UseBoxProjection > 0.5)
                {
                    sampleDir = BoxProjection(
                        direction, worldPosition,
                        _CubemapCapturePosition.xyz,
                        _BoxProjectionMin.xyz,
                        _BoxProjectionMax.xyz
                    );
                }
                
                return texCUBElod(_EnvironmentCubemap, float4(sampleDir, mipLevel)).rgb;
            }
            
            float3 FresnelSchlickRoughness(float cosTheta, float3 F0, float roughness)
            {
                float3 oneMinusRoughness = 1.0 - roughness;
                return F0 + (max(oneMinusRoughness, F0) - F0) * pow(saturate(1.0 - cosTheta), 5.0);
            }
            
            float3 CalculatePBREnvironment(float3 normal, float3 viewDir, float3 worldPosition,
                                           float3 albedo, float metallic, float smoothness)
            {
                float roughness = 1.0 - smoothness;
                float3 reflectDir = reflect(-viewDir, normal);
                float NdotV = saturate(dot(normal, viewDir));
                
                float3 F0 = lerp(0.04, albedo, metallic);
                float3 F = FresnelSchlickRoughness(NdotV, F0, roughness);
                
                float3 kS = F;
                float3 kD = (1.0 - kS) * (1.0 - metallic);
                
                float3 result = 0;
                
                if (_IncludeDiffuse > 0.5)
                {
                    float diffuseMip = max(_CubemapMipLevel, 5.0);
                    float3 irradiance = SampleCubemapWithPosition(normal, worldPosition, diffuseMip);
                    result += kD * irradiance * albedo;
                }
                
                if (_IncludeSpecular > 0.5)
                {
                    float specMip = roughness * 7.0 + _CubemapMipLevel;
                    float3 prefilteredColor = SampleCubemapWithPosition(reflectDir, worldPosition, specMip);
                    float2 envBRDF = float2(
                        saturate(1.0 - roughness + (1.0 - NdotV) * 0.5),
                        roughness * (1.0 - NdotV) * 0.3
                    );
                    result += prefilteredColor * (F * envBRDF.x + envBRDF.y);
                }
                
                return result * _EnvironmentIntensity;
            }
            
            float CalculateFresnelMask(float NdotV)
            {
                if (_UseFresnelMask < 0.5)
                    return 1.0;
                
                float fresnel = pow(1.0 - NdotV, _FresnelPower) * _FresnelScale + _FresnelBias;
                float centerMask = pow(NdotV, _CenterMaskPower);
                float edgeFactor = 1.0 - NdotV;
                float edgeMask = smoothstep(_EdgeThreshold - _EdgeSoftness, 
                                            _EdgeThreshold + _EdgeSoftness, 
                                            edgeFactor);
                
                return saturate(fresnel * edgeMask * (1.0 - centerMask * 0.5));
            }
            
            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.normalWS = UnityObjectToWorldNormal(v.normal);
                return o;
            }
            
            fixed4 frag(v2f i) : SV_Target
            {
                float3 normalWS = normalize(i.normalWS);
                float3 surfaceOffset = normalWS * 1.0;
                float3 worldPosition = _SampleWorldPosition.xyz + surfaceOffset;
                float3 viewDirWS = float3(0, 0, 1);
                float NdotV = saturate(dot(normalWS, viewDirWS));
                
                float3 pbrColor = CalculatePBREnvironment(
                    normalWS, viewDirWS, worldPosition,
                    _BaseColor.rgb, _Metallic, _Smoothness
                );
                
                float fresnelMask = CalculateFresnelMask(NdotV);
                float3 finalColor = lerp(_CenterColor.rgb, pbrColor, fresnelMask);
                float alpha = lerp(_CenterColor.a, 1.0, fresnelMask);
                
                return fixed4(finalColor, alpha);
            }
            
            ENDCG
        }
    }
    
    FallBack Off
}
