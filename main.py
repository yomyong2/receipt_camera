import sys
import cv2
import time
import os
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
    QVBoxLayout, QHBoxLayout, QLineEdit, QSpinBox, QFrame,
    QMessageBox, QStackedWidget
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import (
    QImage, QPixmap
)
import numpy as np
from frame_maker import PhotoFrameMaker
from thermal_printer import ThermalPrinter

class CountdownThread(QThread):
    update_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    
    def run(self):
        for i in range(5, 0, -1):
            self.update_signal.emit(i)
            time.sleep(1)
        self.finished_signal.emit()

class CameraThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = None
        self.preview_mode = False
        
    def run(self):
        for i in range(3):
            try:
                if self.cap is None:
                    self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    
                if not self.cap.isOpened():
                    print(f"카메라 열기 시도 {i+1}...")
                    time.sleep(1)
                    continue
                break
            except Exception as e:
                print(f"카메라 초기화 오류 {i+1}: {str(e)}")
                time.sleep(1)
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret and not self.preview_mode:
                    self.change_pixmap_signal.emit(frame)
                time.sleep(0.03)
            except Exception as e:
                print(f"프레임 읽기 오류: {str(e)}")
                time.sleep(0.1)
    
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()

class PhotoPrinterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.captured_images = []  # 두 장의 사진을 저장할 리스트
        self.current_capture = 0   # 현재 촬영 중인 사진 번호
        self.frame_maker = PhotoFrameMaker()
        self.printer = ThermalPrinter()
        
        self.initUI()
        self.startCamera()
        self.showMaximized()

    def initUI(self):
        self.setWindowTitle('Double Photo Printer')
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 스택 위젯 생성 (카메라 뷰와 미리보기를 전환하기 위함)
        self.stack = QStackedWidget()
        
        # 카메라 뷰 컨테이너
        camera_container = QFrame()
        camera_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                padding: 10px;
            }
        """)
        camera_layout = QVBoxLayout(camera_container)
        
        # 카메라 뷰
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(640, 480)
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                border-radius: 10px;
                padding: 2px;
            }
        """)
        self.camera_label.setAlignment(Qt.AlignCenter)
        camera_layout.addWidget(self.camera_label, alignment=Qt.AlignCenter)
        
        # 미리보기 컨테이너
        preview_container = QFrame()
        preview_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                padding: 10px;
            }
        """)
        preview_layout = QHBoxLayout(preview_container)
        
        # 미리보기 레이블들
        self.preview_label1 = QLabel()
        self.preview_label2 = QLabel()
        for label in [self.preview_label1, self.preview_label2]:
            label.setFixedSize(400, 300)
            label.setStyleSheet("""
                QLabel {
                    background-color: #2c3e50;
                    border-radius: 10px;
                    padding: 2px;
                }
            """)
            label.setAlignment(Qt.AlignCenter)
        
        preview_layout.addWidget(self.preview_label1)
        preview_layout.addWidget(self.preview_label2)
        
        # 스택에 추가
        self.stack.addWidget(camera_container)
        self.stack.addWidget(preview_container)
        layout.addWidget(self.stack)
        
        # 버튼 컨테이너
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        
        self.capture_btn = QPushButton('사진 촬영 시작 (Space)')
        self.capture_btn.clicked.connect(self.start_captures)
        
        self.recapture_btn = QPushButton('다시 촬영 (Esc)')
        self.recapture_btn.clicked.connect(self.restart_capture)
        self.recapture_btn.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.capture_btn)
        button_layout.addWidget(self.recapture_btn)
        button_layout.addStretch()
        
        buttons_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 25px;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        self.capture_btn.setStyleSheet(buttons_style)
        self.recapture_btn.setStyleSheet(buttons_style)
        
        layout.addWidget(button_container)
        
        # 카운트다운 레이블
        self.countdown_label = QLabel('')
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet('font-size: 36pt; color: #2ecc71; font-weight: bold;')
        layout.addWidget(self.countdown_label)
        
        # 입력 컨테이너
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        input_layout = QVBoxLayout(input_container)
        
        # 텍스트 입력
        text_label = QLabel('메시지 입력')
        text_label.setStyleSheet('font-weight: bold; color: #34495e;')
        
        text_input_layout = QHBoxLayout()
        text_input_layout.setSpacing(10)  # 위젯 간 간격 조정
        
        # 텍스트 입력 필드를 포함할 컨테이너
        text_container = QFrame()
        text_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: none;
                margin: 0;
                padding: 0;
            }
        """)
        text_container_layout = QHBoxLayout(text_container)
        text_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText('텍스트를 입력하세요')
        self.text_input.setMinimumHeight(45)  # 버튼과 같은 높이로 설정
        
        self.random_msg_btn = QPushButton('🎲')  # 아이콘만 표시
        self.random_msg_btn.setFixedSize(45, 45)  # 정사각형 버튼
        self.random_msg_btn.clicked.connect(lambda: self.text_input.setText(self.get_random_message()))
        self.random_msg_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        text_container_layout.addWidget(self.text_input)
        text_container_layout.addWidget(self.random_msg_btn)
        
        text_input_layout.addWidget(text_container)
        
        input_layout.addWidget(text_label)
        input_layout.addLayout(text_input_layout)

        # 인쇄 매수 입력
        copies_layout = QHBoxLayout()
        copies_label = QLabel('인쇄 매수:')
        copies_label.setStyleSheet('font-weight: bold; color: #34495e;')
        self.copies_spinbox = QSpinBox()
        self.copies_spinbox.setMinimum(1)
        self.copies_spinbox.setMaximum(10)
        copies_layout.addWidget(copies_label)
        copies_layout.addWidget(self.copies_spinbox)
        copies_layout.addStretch()
        input_layout.addLayout(copies_layout)
        
        # 인쇄 버튼
        self.print_btn = QPushButton('인쇄하기')
        self.print_btn.clicked.connect(self.print_image)
        self.print_btn.setEnabled(False)
        self.print_btn.setStyleSheet(buttons_style)
        input_layout.addWidget(self.print_btn, alignment=Qt.AlignCenter)
        
        layout.addWidget(input_container)
        
        # 카운트다운 스레드
        self.countdown_thread = CountdownThread()
        self.countdown_thread.update_signal.connect(self.update_countdown)
        self.countdown_thread.finished_signal.connect(self.capture_image)
        
        # 키보드 포커스 정책 설정
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 전체 스타일시트 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QLabel {
                color: #2c3e50;
                font-size: 14px;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                font-size: 14px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QSpinBox {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                min-width: 80px;
                min-height: 20px;
            }
            QSpinBox:focus {
                border: 2px solid #3498db;
            }
        """)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            # 스페이스바: 촬영 시작 또는 미리보기 상태에서는 무시
            if self.capture_btn.isEnabled():
                self.start_captures()
        elif event.key() == Qt.Key_Escape:
            # ESC: 다시 촬영
            if self.recapture_btn.isEnabled():
                self.restart_capture()
        event.accept()

    def get_random_message(self):
        messages = [
            "행복한 하루가 될 예정이에요!",
            "좋은 일이 생길 거예요!",
            "오늘은 행운의 날이에요!",
            "재미있는 하루가 될 거예요!"
        ]
        return random.choice(messages)

    def startCamera(self):
        self.camera_thread = CameraThread()
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.start()

    @pyqtSlot(np.ndarray)
    def update_image(self, frame):
        qt_img = self.convert_cv_qt(frame)
        self.camera_label.setPixmap(qt_img)

    def convert_cv_qt(self, frame, target_width=640, target_height=480):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled = convert_to_Qt_format.scaled(target_width, target_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(scaled)

    def start_captures(self):
        self.captured_images = []
        self.current_capture = 0
        self.capture_btn.setEnabled(False)
        self.stack.setCurrentIndex(0)  # 카메라 뷰로 전환
        self.start_countdown()

    def start_countdown(self):
        self.countdown_thread = CountdownThread()
        self.countdown_thread.update_signal.connect(self.update_countdown)
        self.countdown_thread.finished_signal.connect(self.capture_image)
        self.countdown_thread.start()

    @pyqtSlot(int)
    def update_countdown(self, value):
        self.countdown_label.setText(str(value))

    def capture_image(self):
        if hasattr(self.camera_thread, 'cap') and self.camera_thread.cap is not None:
            ret, frame = self.camera_thread.cap.read()
            if ret:
                # 흑백으로 변환
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # 현재 캡처 번호에 따라 저장
                filename = f'temp_capture_{self.current_capture + 1}.png'
                cv2.imwrite(filename, gray_frame)
                self.captured_images.append(filename)
                
                # 미리보기 업데이트
                preview_img = self.convert_cv_qt(cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR), 400, 300)  # 미리보기 크기 조정
                if self.current_capture == 0:
                    self.preview_label1.setPixmap(preview_img)
                    self.current_capture = 1
                    self.countdown_label.setText('5초 후 두 번째 사진')
                    time.sleep(5)  # 5초 대기
                    self.start_countdown()
                else:
                    self.preview_label2.setPixmap(preview_img)
                    self.camera_thread.preview_mode = True
                    self.stack.setCurrentIndex(1)  # 미리보기로 전환
                    self.capture_btn.setEnabled(False)
                    self.recapture_btn.setEnabled(True)
                    self.print_btn.setEnabled(True)
                    self.countdown_label.setText('')

    def restart_capture(self):
        self.camera_thread.preview_mode = False
        self.stack.setCurrentIndex(0)  # 카메라 뷰로 전환
        self.capture_btn.setEnabled(True)
        self.print_btn.setEnabled(False)
        self.recapture_btn.setEnabled(False)
        self.captured_images = []
        self.current_capture = 0
        
        # 미리보기 레이블 초기화
        blank_pixmap = QPixmap(400, 300)
        blank_pixmap.fill(Qt.black)
        self.preview_label1.setPixmap(blank_pixmap)
        self.preview_label2.setPixmap(blank_pixmap)

    def print_image(self):
        try:
            # 두 이미지를 하나의 프레임으로 만들기
            framed_image_path = self.frame_maker.create_double_frame(
                self.captured_images[0],
                self.captured_images[1],
                self.text_input.text()
            )
            
            # 이미지 인쇄
            copies = self.copies_spinbox.value()
            self.printer.print_image(framed_image_path, copies)
            
            QMessageBox.information(self, '완료', '인쇄가 완료되었습니다.')
            
            # UI 초기화
            self.camera_thread.preview_mode = False
            self.stack.setCurrentIndex(0)  # 카메라 뷰로 전환
            self.capture_btn.setEnabled(True)
            self.print_btn.setEnabled(False)
            self.recapture_btn.setEnabled(False)
            
            # 미리보기 레이블 초기화
            blank_pixmap = QPixmap(400, 300)
            blank_pixmap.fill(Qt.black)
            self.preview_label1.setPixmap(blank_pixmap)
            self.preview_label2.setPixmap(blank_pixmap)
            
            # 상태 초기화
            self.captured_images = []
            self.current_capture = 0
            
            # 임시 파일 삭제
            for file in self.captured_images + [framed_image_path]:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except Exception as e:
                    print(f"파일 삭제 중 오류 발생: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, '에러', f'인쇄 중 오류가 발생했습니다: {str(e)}')

    def closeEvent(self, event):
        # 카메라 정지
        self.camera_thread.stop()
        
        # 임시 파일 삭제
        for file in self.captured_images:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except Exception as e:
                print(f"파일 삭제 중 오류 발생: {str(e)}")
        
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PhotoPrinterApp()
    ex.show()
    sys.exit(app.exec_())