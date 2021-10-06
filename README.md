# MLOps-Example
Original repository & [Blog](https://byeongjo-kim.tistory.com/7)

## System Design
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/system_design.png)

##### 참고 
##### [MLOps 수준 2: CI/CD 파이프라인 자동화](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning#mlops_level_2_cicd_pipeline_automation)

##### [Kubeflow Pipelines를 사용한 ML을 위한 CI/CD 개요](https://cloud.google.com/architecture/architecture-for-mlops-using-tfx-kubeflow-pipelines-and-cloud-build#cicd_architecture)
        
## CI/CD
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/cicd0.png)

![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/cicd1.png)

### CI
- [yaml file](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/.github/workflows/ci.yml)
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:          
      - name: Check out
        uses: actions/checkout@v2
      
      - name: Docker Login
        uses: docker/login-action@v1.8.0
        with:
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Build Images
        run: |
          docker build kubeflow_pipeline/0_data -t byeongjokim/mnist-pre-data
          ..(생략)..
          docker push byeongjokim/mnist-deploy
      
      - name: Slack Notification
        if: always()
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_ICON_EMOJI: ':bell:'
          SLACK_CHANNEL: mnist-project
          SLACK_MESSAGE: 'Build/Push Images :building_construction: - ${{job.status}}'
          SLACK_USERNAME: Github
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK_URL }}
```    
    
#  
- GitHub actions에서 사용할 secrets(보안이 필요한 정보) 등록 필요
  repository settings -> secrets -> New repository Secret
 
    KUBERNETES_HOST: 쿠버네티스 클러스터 접속정보
    PIPELINE_NAMESPACE: 파이프라인 배포할 네임스페이스
    PIPELINE_USER_NAME: 쿠버네티스 클러스터 접속 유저명
    PIPELINE_USER_PASS: 쿠버네티스 클러스터 접속 유저아이디
    REGISTRY_PASSWORD: 이미지 저장소(도커) 패스워드
    REGISTRY_USERNAME: 이미지 저장소(도커) 유저아이디
    SLACK_WEBHOOK_URL: slack app을 통해 생성한 webhook urㅣ
                       참고 (https://helloworld.kurly.com/blog/slack_block_kit/)


### CD
- [yaml file](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/.github/workflows/cd.yml)
```yaml
name: CD

on:
  workflow_run:
    workflows: ["ci"]
    branches: [main]
    types: 
      - completed

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:          
      - name: Check out
        uses: actions/checkout@v2
          
      - uses: actions/setup-python@v2
        with:
          python-version: '3.6.12'
          architecture: x64
      
      - uses: BSFishy/pip-action@v1
        with:
          packages: |
            kfp==1.3.0
      - name: run pipeline to kubeflow
        run: python kubeflow_pipeline/pipeline.py

      - name: Slack Notification
        if: always()
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_ICON_EMOJI: ':bell:'
          SLACK_CHANNEL: mnist-project
          SLACK_MESSAGE: 'Upload & Run pipeline :rocket: - ${{job.status}}'
          SLACK_USERNAME: Github
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## CT
### alert using slack when new data is coming
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/ct1.png)
- using Slack Trigger (slack_sdk)
- private repository in Github..
- when to train?
    - every Tuesday
    - new data is coming


## kubeflow pipelines
- 0_data
    - **data 수집**
    - **전처리 후 npy 저장(train/test/validation)**
    - npy_interval 사용하여 데이터 나누어 저장
    - embedding 학습에 사용하는 데이터와 faiss 학습 시 사용되는 데이터 구분
- 1_validate_data
    - **전처리된 npy 검증**
    - shape, type 등 전처리 결과 확인
- 2_train_model
    - **embedding 모델 학습**
    - ArcFace 사용
    - multip gpu 사용
    - 학습 완료된 모델 torch.jit.script 저장
- 3_embedding
    - faiss 사용될 데이터 **embedding 전처리 후 npy 저장**
    - torch.jit.script 저장된 모델 load 해서 사용
- 4_train_faiss
    - embedding npy로 **faiss 학습**
    - faiss index 저장
- 5_analysis_model
    - **전체 모델 성능 평가**
    - mlpipeline-metrics, mlpipeline-ui-metadata로 시각화
    - class 별 accuracy 측정 (confusion matrix)
    - dsl.Condition 사용하여 배포할지 결정
- 6_deploy
    - 모델 버전 관리
    - config 관리
    - service, deployment 배포
    - torchserve 사용

### Serving Model using TorchServe
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/serving.png)

##### 이 예제에서는 훈련된 모델의 배포까지 ML파이프라인에서 하지만 일반적인 머신러닝 조직에서는 ML파이프라인에서 배포까지 자동화 하진 않는것으로 보이니 참고할것
```
.....
그러나 이와 같이 완전한 파이프라인을 만드는 것은 모든 조직에서 실용적이지 않을 수 있습니다. 예를 들어 일부 조직에서는 모델 교육 및 모델 배포가 다른 팀의 책임입니다. 따라서 범위
대부분의 훈련 파이프라인은 서비스를 위해 배포하는 것이 아니라 훈련되고 검증된 모델을 등록하는 것으로 끝납니다.

from Practitioners guide to MLOps/Google 2021
```

### uploaded pipelines
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/pipelines0.png)

- [kubeflow pipeline architectural-overview](https://www.kubeflow.org/docs/components/pipelines/overview/pipelines-overview/#architectural-overview)
- [v1 SDK: Writing out metadata for the output viewers](https://www.kubeflow.org/docs/components/pipelines/sdk/output-viewer/#v1-sdk-writing-out-metadata-for-the-output-viewers)
- [파이프라인 메트릭 내보내기 및 시각화](https://www.kubeflow.org/docs/components/pipelines/sdk/pipelines-metrics/)
- [도커 이미지 빌드 없이 파이썬 함수에서 컴포넌트생성 방법(경량화된 컴포넌트)](https://github.com/kubeflow/pipelines/blob/master/samples/core/lightweight_component/lightweight_component.ipynb)

### confusion matrix(mlpipeline-ui-metadata)
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/pipelines1.png)

### alrert results using slack
![png](https://raw.githubusercontent.com/byeongjokim/MLOps-Example/main/png/pipelines2.png)