from PIL import Image, ImageDraw, ImageOps, ImageFont
import os

class PhotoFrameMaker:
    def __init__(self):
        font_path = "Binggrae.ttf"
        if not os.path.exists(font_path):
            raise Exception("Binggrae.ttf 폰트 파일이 필요합니다.")
        
        self.title_font = ImageFont.truetype(font_path, 28)
        self.content_font = ImageFont.truetype(font_path, 32)

    def create_double_frame(self, image1_path, image2_path, text=None):
        try:
            # 이미지 열기
            img1 = Image.open(image1_path)
            img2 = Image.open(image2_path)
            
            # 각 이미지 리사이징
            base_width = 576  # 72mm * 8dots/mm = 576 dots
            base_height = int((base_width * img1.height) / img1.width)
            
            img1 = img1.resize((base_width, base_height), Image.Resampling.LANCZOS)
            img2 = img2.resize((base_width, base_height), Image.Resampling.LANCZOS)
            
            # 여백 설정
            spacing = 40  # 사진 간격 0.5cm
            text_area_height = 120  # 텍스트 영역
            
            # 전체 높이 계산
            total_height = base_height * 2 + spacing + text_area_height
            
            # 새 이미지 생성
            new_img = Image.new('L', (base_width, total_height), 'white')
            
            # 이미지 붙이기
            new_img.paste(img1, (0, 0))
            new_img.paste(img2, (0, base_height + spacing))
            
            # 텍스트 추가
            draw = ImageDraw.Draw(new_img)
            
            if text is None or text.strip() == "":
                text = "행복한 하루 되세요!"
            
            text_x = base_width // 2
            text_y = total_height - (text_area_height // 2)
            
            draw.text(
                (text_x, text_y),
                text,
                font=self.content_font,
                fill="black",
                anchor="mm",
                align="center"
            )
            
            # 이미지 저장
            save_path = "print_double_frame.png"
            new_img.save(save_path)
            return save_path
            
        except Exception as e:
            raise Exception(f"프레임 생성 중 오류 발생: {str(e)}")

    def create_frame(self, image_path, text=None):
        """기존의 단일 이미지 프레임 생성 메소드 (하위 호환성 유지)"""
        try:
            img = Image.open(image_path)
            
            base_width = 576
            base_height = int((base_width * img.height) / img.width)
            img = img.resize((base_width, base_height), Image.Resampling.LANCZOS)
            
            text_area_height = 120
            new_img = ImageOps.expand(img, border=(0, 0, 0, text_area_height), fill="white")
            draw = ImageDraw.Draw(new_img)
            
            if text is None or text.strip() == "":
                text = "행복한 하루 되세요!"
            
            text_x = new_img.width // 2
            text_y = img.height + text_area_height // 2
            
            draw.text(
                (text_x, text_y),
                text,
                font=self.content_font,
                fill="black",
                anchor="mm",
                align="center"
            )
            
            save_path = "print_" + os.path.basename(image_path)
            new_img.save(save_path)
            return save_path
            
        except Exception as e:
            raise Exception(f"프레임 생성 중 오류 발생: {str(e)}")