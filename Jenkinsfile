stage('1.0 accountingservice') {
    steps {
        buildAndPushDockerImage('accountingservice')
    }
}

def buildAndPushDockerImage(serviceName) {
    script {
        withDockerRegistry(credentialsId: 'docker', toolName: 'docker') {
            def dockerfilePath = "/root/appnode/workspace/otp/src/${serviceName}/Dockerfile"
            def imageName = "iscanprint/${serviceName}:3.0"
            
            dir("/root/appnode/workspace/otp/src/${serviceName}/") {
                sh "docker build -t ${imageName} -f ${dockerfilePath} ."
                sh "docker push ${imageName}"
                sh "docker rmi -f ${imageName}"
            }
        }
    }
}
