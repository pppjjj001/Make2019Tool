# blue_noise_generator.py
"""
蓝噪声纹理生成工具
使用 Void-and-Cluster 算法生成高质量蓝噪声
"""

import numpy as np
from PIL import Image
import os
import sys
from datetime import datetime

class BlueNoiseGenerator:
    def __init__(self, size=64, seed=None):
        """
        初始化蓝噪声生成器
        
        Args:
            size: 纹理尺寸 (正方形)
            seed: 随机种子，None 则使用时间戳
        """
        self.size = size
        self.seed = seed if seed is not None else int(datetime.now().timestamp())
        np.random.seed(self.seed)
        
    def generate_white_noise(self):
        """生成白噪声作为初始"""
        return np.random.rand(self.size, self.size)
    
    def apply_gaussian_filter(self, data, sigma=1.5):
        """应用高斯滤波"""
        from scipy.ndimage import gaussian_filter
        return gaussian_filter(data, sigma=sigma, mode='wrap')
    
    def void_and_cluster(self, iterations=100):
        """
        Void-and-Cluster 算法生成蓝噪声
        这是最经典的蓝噪声生成算法
        """
        print(f"开始生成 {self.size}x{self.size} 蓝噪声...")
        print(f"随机种子: {self.seed}")
        
        # 初始化随机二值图
        binary_pattern = np.random.rand(self.size, self.size) > 0.5
        binary_pattern = binary_pattern.astype(float)
        
        # 迭代优化
        for iteration in range(iterations):
            if iteration % 10 == 0:
                print(f"迭代进度: {iteration}/{iterations}")
            
            # 计算能量图（高斯滤波）
            energy = self.apply_gaussian_filter(binary_pattern, sigma=1.5)
            
            # 找到最大能量的 1 点（cluster）
            ones_mask = binary_pattern > 0.5
            if np.any(ones_mask):
                energy_ones = energy.copy()
                energy_ones[~ones_mask] = -np.inf
                cluster_pos = np.unravel_index(np.argmax(energy_ones), energy.shape)
                
                # 找到最小能量的 0 点（void）
                zeros_mask = binary_pattern < 0.5
                if np.any(zeros_mask):
                    energy_zeros = energy.copy()
                    energy_zeros[~zeros_mask] = np.inf
                    void_pos = np.unravel_index(np.argmin(energy_zeros), energy.shape)
                    
                    # 交换
                    binary_pattern[cluster_pos] = 0
                    binary_pattern[void_pos] = 1
        
        print("生成完成！")
        return binary_pattern
    
    def generate_multi_channel(self, channels=2):
        """生成多通道蓝噪声（用于 2D 采样）"""
        print(f"生成 {channels} 通道蓝噪声...")
        
        result = np.zeros((self.size, self.size, channels))
        
        for i in range(channels):
            print(f"\n--- 通道 {i+1}/{channels} ---")
            # 每个通道用不同的种子
            self.seed = self.seed + i * 1000
            np.random.seed(self.seed)
            result[:, :, i] = self.void_and_cluster(iterations=100)
        
        return result
    
    def save_texture(self, data, filename, format='PNG'):
        """保存为图片文件"""
        # 归一化到 0-255
        if data.ndim == 2:
            # 单通道，转为灰度图
            img_data = (data * 255).astype(np.uint8)
            img = Image.fromarray(img_data, mode='L')
        else:
            # 多通道
            img_data = (data * 255).astype(np.uint8)
            if data.shape[2] == 2:
                # 2 通道，补一个通道变成 RGB
                img_data = np.dstack([img_data, np.zeros((self.size, self.size), dtype=np.uint8)])
            img = Image.fromarray(img_data, mode='RGB')
        
        img.save(filename, format=format)
        print(f"\n✓ 已保存: {filename}")
        print(f"  尺寸: {self.size}x{self.size}")
        print(f"  通道: {data.shape[2] if data.ndim == 3 else 1}")
        print(f"  格式: {format}")


def generate_simple_blue_noise(size=64):
    """
    简化版蓝噪声生成（不依赖 scipy）
    使用频域滤波方法
    """
    print(f"使用简化算法生成 {size}x{size} 蓝噪声...")
    
    # 生成白噪声
    white = np.random.rand(size, size)
    
    # FFT 到频域
    fft = np.fft.fft2(white)
    fft_shifted = np.fft.fftshift(fft)
    
    # 创建高通滤波器（保留高频，去除低频）
    center = size // 2
    y, x = np.ogrid[:size, :size]
    distance = np.sqrt((x - center)**2 + (y - center)**2)
    
    # 高通滤波器：距离中心越远权重越大
    high_pass = distance / (size / 2)
    high_pass = np.clip(high_pass, 0, 1)
    
    # 应用滤波
    fft_filtered = fft_shifted * high_pass
    
    # 逆 FFT 回空域
    ifft = np.fft.ifftshift(fft_filtered)
    result = np.fft.ifft2(ifft).real
    
    # 归一化到 [0, 1]
    result = (result - result.min()) / (result.max() - result.min())
    
    print("生成完成！")
    return result


def main():
    print("=" * 60)
    print("           蓝噪声纹理生成工具 v1.0")
    print("=" * 60)
    print()
    
    # 检查是否安装了 scipy
    try:
        import scipy
        use_advanced = True
        print("✓ 检测到 scipy，使用高级算法 (Void-and-Cluster)")
    except ImportError:
        use_advanced = False
        print("⚠ 未安装 scipy，使用简化算法 (FFT 高通滤波)")
        print("  提示: 运行 'pip install scipy' 可获得更好效果")
    
    print()
    
    # 用户输入
    try:
        size_input = input("请输入纹理尺寸 (推荐 64/128/256，默认 64): ").strip()
        size = int(size_input) if size_input else 64
        
        channels_input = input("请输入通道数 (1=灰度, 2=RG, 默认 2): ").strip()
        channels = int(channels_input) if channels_input else 2
        
        count_input = input("生成数量 (默认 1): ").strip()
        count = int(count_input) if count_input else 1
        
    except ValueError:
        print("✗ 输入无效，使用默认值")
        size = 64
        channels = 2
        count = 1
    
    print()
    print(f"配置: {size}x{size}, {channels}通道, 生成 {count} 张")
    print("-" * 60)
    print()
    
    # 创建输出目录
    output_dir = "BlueNoise_Output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成
    for i in range(count):
        print(f"\n{'='*60}")
        print(f"生成第 {i+1}/{count} 张")
        print(f"{'='*60}\n")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if use_advanced:
            generator = BlueNoiseGenerator(size=size)
            
            if channels == 1:
                data = generator.void_and_cluster(iterations=100)
            else:
                data = generator.generate_multi_channel(channels=channels)
            
            filename = os.path.join(output_dir, f"BlueNoise_{size}x{size}_C{channels}_{timestamp}_{i+1}.png")
            generator.save_texture(data, filename)
        else:
            # 简化算法
            if channels == 1:
                data = generate_simple_blue_noise(size)
            else:
                data = np.zeros((size, size, channels))
                for c in range(channels):
                    print(f"通道 {c+1}/{channels}...")
                    np.random.seed(int(datetime.now().timestamp()) + c * 1000)
                    data[:, :, c] = generate_simple_blue_noise(size)
            
            filename = os.path.join(output_dir, f"BlueNoise_{size}x{size}_C{channels}_{timestamp}_{i+1}.png")
            
            # 保存
            if data.ndim == 2:
                img_data = (data * 255).astype(np.uint8)
                img = Image.fromarray(img_data, mode='L')
            else:
                img_data = (data * 255).astype(np.uint8)
                if data.shape[2] == 2:
                    img_data = np.dstack([img_data, np.zeros((size, size), dtype=np.uint8)])
                img = Image.fromarray(img_data, mode='RGB')
            
            img.save(filename)
            print(f"\n✓ 已保存: {filename}")
    
    print()
    print("=" * 60)
    print(f"✓ 全部完成！文件保存在: {os.path.abspath(output_dir)}")
    print("=" * 60)
    print()
    input("按回车键退出...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
        sys.exit(1)