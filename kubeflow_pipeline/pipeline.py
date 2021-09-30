import os
import argparse
import kfp
import kfp.components as comp
from kfp import dsl
from kfp import onprem
from kubernetes import client as k8s_client
from kubernetes.client.models import V1EnvVar
import requests

@dsl.pipeline(
    name="mnist using arcface",
    description="CT pipeline"
)
def mnist_pipeline(manage_url):
    ENV_MANAGE_URL = V1EnvVar(name='MANAGE_URL', value=manage_url)

    data_0 = dsl.ContainerOp(
        name="load & preprocess data pipeline",
        image="goldenbell1/mnist-pre-data:latest",
    ).set_display_name('collect & preprocess data')\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))

    data_1 = dsl.ContainerOp(
        name="validate data pipeline",
        image="goldenbell1/mnist-val-data:latest",
    ).set_display_name('validate data').after(data_0)\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))

    train_model = dsl.ContainerOp(
        name="train embedding model",
        image="goldenbell1/mnist-train-model:latest",
    ).set_display_name('train model').after(data_1)\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))\
    .apply(onprem.mount_pvc("train-model-pvc", volume_name="train-model", volume_mount_path="/model"))

    embedding = dsl.ContainerOp(
        name="embedding data using embedding model",
        image="goldenbell1/mnist-embedding:latest",
    ).set_display_name('embedding').after(train_model)\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))\
    .apply(onprem.mount_pvc("train-model-pvc", volume_name="train-model", volume_mount_path="/model"))

    train_faiss = dsl.ContainerOp(
        name="train faiss",
        image="goldenbell1/mnist-train-faiss:latest",
    ).set_display_name('train faiss').after(embedding)\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))\
    .apply(onprem.mount_pvc("train-model-pvc", volume_name="train-model", volume_mount_path="/model"))

    analysis = dsl.ContainerOp(
        name="analysis total",
        image="goldenbell1/mnist-analysis:latest",
        file_outputs={
            "confusion_matrix": "/confusion_matrix.csv",
            "mlpipeline-ui-metadata": "/mlpipeline-ui-metadata.json",
            "accuracy": "/accuracy.json",
            "mlpipeline_metrics": "/mlpipeline-metrics.json"
        }
    ).add_env_variable(ENV_MANAGE_URL).set_display_name('analysis').after(train_faiss)\
    .apply(onprem.mount_pvc("data-pvc", volume_name="data", volume_mount_path="/data"))\
    .apply(onprem.mount_pvc("train-model-pvc", volume_name="train-model", volume_mount_path="/model"))

    baseline = 0.8
    with dsl.Condition(analysis.outputs["accuracy"] > baseline) as check_deploy:
        deploy = dsl.ContainerOp(
            name="deploy mar",
            image="goldenbell1/mnist-deploy:latest",
        ).add_env_variable(ENV_MANAGE_URL).set_display_name('deploy').after(analysis)\
        .apply(onprem.mount_pvc("train-model-pvc", volume_name="train-model", volume_mount_path="/model"))\
        .apply(onprem.mount_pvc("deploy-model-pvc", volume_name="deploy-model", volume_mount_path="/deploy-model"))

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default="")
    
    parser.add_argument('--namespace', type=str, default='')
    parser.add_argument('--username', type=str, default='')
    parser.add_argument('--password', type=str, default='')
    parser.add_argument('--manage_url', type=str, default='')

    args = parser.parse_args()
    
    session = requests.Session()
    response = session.get(args.host)

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"login": args.username, "password": args.password}
    session.post(response.url, headers=headers, data=data)
    session_cookie = session.cookies.get_dict()["authservice_session"]
    
    
    pipeline_name = "Mnist"
    pipeline_package_path = "pipeline.zip"
    version = "v0.3.1"

    experiment_name = "For Develop"
    run_name = "kubeflow study {}".format(version)
     
    client = kfp.Client(host=f"{args.host}/pipeline", namespace=args.namespace, cookies=f"authservice_session={session_cookie}").create_run_from_pipeline_func(mnist_pipeline, arguments={args.manage_url})
    #kfp.compiler.Compiler().compile(mnist_pipeline(args.manage_url), pipeline_package_path)

    pipeline_id = client.get_pipeline_id(pipeline_name)
    if pipeline_id:
        client.upload_pipeline_version(
            pipeline_package_path=pipeline_package_path,
            pipeline_version_name=version,
            pipeline_name=pipeline_name
        )
    else:
        client.upload_pipeline(
            pipeline_package_path=pipeline_package_path,
            pipeline_name=pipeline_name
        )
    
    experiment = client.create_experiment(name=experiment_name, namespace=args.namespace)
    run = client.run_pipeline(experiment.id, run_name, pipeline_package_path)