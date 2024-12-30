from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import cv2
import serial
import time

class ThermalPrinter:
    def __init__(self, port='COM7', baudrate=115200):
        self.max_width = 576  # 72mm * 8dots/mm = 576 dots
        self._initialize_printer(port, baudrate)
    
    def _initialize_printer(self, port, baudrate):
        """프린터를 초기화합니다."""
        self.printer_dev = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=30,
            write_timeout=30,
            xonxoff=True
        )
        
        # 프린터 초기화 명령
        commands = [
            [0x1B, 0x40],      # Initialize printer
            [0x1B, 0x33, 0],   # Set line spacing to 0
        ]
        for cmd in commands:
            self._write_bytes(cmd)

    def _enhance_image(self, img):
        """인물 사진에 최적화된 이미지 품질 향상"""
        # 노이즈 제거 (아주 약하게)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # 선명도 향상 (인물의 디테일 보존)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        img = img.filter(ImageFilter.DETAIL)
        
        # 밝기와 대비 (약하게 조정)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)  # 10% 밝기 증가
        
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)  # 15% 대비 증가
        
        return img

    def _write_bytes(self, data):
        self.printer_dev.write(bytes(data))
        self.printer_dev.flush()

    def print_image(self, image_path, copies=1):
        try:
            for copy in range(copies):
                self._print_single_image(image_path)
                self.cut_paper()
                if copy < copies - 1:
                    time.sleep(1)
        except Exception as e:
            raise Exception(f"인쇄 중 오류 발생: {str(e)}")

    def _print_single_image(self, image_path):
        with open(image_path, 'rb') as f:
            # 이미지 열기
            img = Image.open(f)
            
            # 이미지가 이미 흑백이 아닌 경우에만 전처리
            if img.mode != 'L':
                img = img.convert('L')
            
            # 이미지 품질 향상
            img = self._enhance_image(img)
            
            # 크기 조정 (디테일 보존을 위해 단계적으로)
            target_width = self.max_width
            orig_w, orig_h = img.size
            target_height = int((orig_h * target_width) / orig_w)
            
            # 2단계 리사이징으로 디테일 보존
            intermediate_w = int(target_width * 1.5)
            intermediate_h = int(target_height * 1.5)
            img = img.resize((intermediate_w, intermediate_h), Image.Resampling.LANCZOS)
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # 향상된 디더링으로 흑백 변환
            img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
            pixels = np.array(img)
            
            # 프린터 명령어 전송
            width_bytes = (target_width + 7) // 8
            
            # GS v 0 command
            self._write_bytes([0x1D, 0x76, 0x30, 0])
            self._write_bytes([
                width_bytes & 0xFF,
                (width_bytes >> 8) & 0xFF,
                target_height & 0xFF,
                (target_height >> 8) & 0xFF
            ])
            
            # 이미지 데이터 전송
            image_data = []
            for y in range(target_height):
                for x in range(0, target_width, 8):
                    byte_val = 0
                    for bit in range(min(8, target_width - x)):
                        if x + bit < target_width and pixels[y, x + bit] == 0:
                            byte_val |= (1 << (7 - bit))
                    image_data.append(byte_val)
            
            self._write_bytes(image_data)
            self._write_bytes([0x0A] * 4)

    def cut_paper(self):
        self._write_bytes([0x0A] * 6)
        time.sleep(1)
        self._write_bytes([0x1D, 0x56, 0x41, 0x40])
        time.sleep(0.5)
        
    def __del__(self):
        if hasattr(self, 'printer_dev') and self.printer_dev and self.printer_dev.is_open:
            self.printer_dev.close()