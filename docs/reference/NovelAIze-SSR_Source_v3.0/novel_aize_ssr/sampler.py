import os

class Sampler:
    """
    대용량 텍스트 파일에서 대표성 있는 샘플을 추출하는 클래스.
    전체 파일을 다 읽지 않고, 파일의 여러 지점(offset)에서 조각(chunk)을 읽어 합칩니다.
    """
    def __init__(self, chunk_size=32768, num_samples=30):
        """
        :param chunk_size: 각 샘플링 지점에서 읽을 바이트 수 (기본 32KB)
        :param num_samples: 샘플링할 지점의 개수 (기본 20개, 총 640KB)
        """
        self.chunk_size = chunk_size
        self.num_samples = num_samples

    def extract_samples(self, file_path: str) -> str:
        """
        파일에서 샘플 텍스트를 추출하여 하나의 문자열로 반환합니다.
        
        :param file_path: 대상 파일 경로
        :return: 병합된 샘플 텍스트
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        samples = []

        # 1. 파일 크기가 작으면 전체 통째로 읽기 (약 500KB 이하)
        # (chunk_size * num_samples 보다 작으면 그냥 다 읽는게 낫다)
        total_sample_size = self.chunk_size * self.num_samples
        if file_size <= total_sample_size * 1.5: 
             with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                 return f.read()

        # 2. 대용량 파일 샘플링
        step = file_size // self.num_samples
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # 첫 부분은 무조건 포함 (프롤로그 확인용)
            samples.append(f.read(self.chunk_size))
            
            # 중간 지점들 순회
            for i in range(1, self.num_samples):
                offset = i * step
                f.seek(offset)
                
                # seek로 이동했을 때 한글 글자 중간에 떨어지면 깨질 수 있음.
                # errors='ignore'로 읽거나, 안전하게 readline()을 한번 호출하여 줄 맞춤을 할 수도 있음.
                # 여기서는 readline()으로 줄 바꿈을 한번 버리고 그 다음부터 읽는 전략 사용.
                f.readline() 
                
                chunk = f.read(self.chunk_size)
                if chunk:
                    samples.append(chunk)

        # 구분선으로 합쳐서 반환
        return "\n\n[...SAMPLE_SKIP...]\n\n".join(samples)

    def extract_samples_from(self, file_path: str, start_offset: int) -> str:
        """
        파일의 특정 지점부터 끝까지 범위 내에서 샘플링합니다.
        
        :param file_path: 파일 경로
        :param start_offset: 샘플링 시작 위치 (byte offset)
        :return: 병합된 샘플 텍스트
        """
        if not os.path.exists(file_path):
             return ""

        file_size = os.path.getsize(file_path)
        remaining_size = file_size - start_offset
        
        if remaining_size <= 0:
            return ""

        # 남은 크기가 작으면 다 읽음 (2MB 이하면 통으로)
        if remaining_size < 2 * 1024 * 1024:
             with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                 f.seek(start_offset)
                 f.readline() # 안전하게 첫 줄 버림
                 return f.read()

        # 남은 크기가 크면 구간 샘플링 (10개)
        num_retry_samples = 10
        step = remaining_size // num_retry_samples
        samples = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
             # 시작 부분
             f.seek(start_offset)
             f.readline()
             first_chunk = f.read(self.chunk_size)
             samples.append(first_chunk)
             
             for i in range(1, num_retry_samples):
                 offset = start_offset + (i * step)
                 f.seek(offset)
                 f.readline()
                 chunk = f.read(self.chunk_size)
                 if chunk:
                     samples.append(chunk)

        return "\n\n[...RETRY_SAMPLE_SKIP...]\n\n".join(samples)

