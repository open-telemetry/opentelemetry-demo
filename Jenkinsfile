// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

pipeline {
    agent any

    environment {
        // GCP project & registry config — set these in Jenkins credentials/env
        GCP_PROJECT      = credentials('GCP_PROJECT_ID')
        GCP_REGION       = 'us-central1'
        REGISTRY         = "gcr.io/${GCP_PROJECT}"
        IMAGE_TAG        = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'local'}"

        // Service names and their Dockerfile paths (relative to repo root)
        ACCOUNTING_IMAGE = "${REGISTRY}/accounting"
        CART_IMAGE       = "${REGISTRY}/cart"
    }

    parameters {
        choice(
            name: 'SERVICES',
            choices: ['all', 'accounting', 'cart'],
            description: 'Which .NET service(s) to build and push'
        )
        string(
            name: 'CUSTOM_TAG',
            defaultValue: '',
            description: 'Override the image tag (leave blank to use build number + git SHA)'
        )
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Resolve Tag') {
            steps {
                script {
                    env.FINAL_TAG = params.CUSTOM_TAG?.trim() ? params.CUSTOM_TAG.trim() : env.IMAGE_TAG
                    echo "Image tag: ${env.FINAL_TAG}"
                }
            }
        }

        stage('Authenticate to GCR') {
            steps {
                withCredentials([file(credentialsId: 'GCP_SERVICE_ACCOUNT_KEY', variable: 'GCP_KEY_FILE')]) {
                    sh '''
                        gcloud auth activate-service-account --key-file="${GCP_KEY_FILE}"
                        gcloud auth configure-docker gcr.io --quiet
                    '''
                }
            }
        }

        stage('Build & Push: Accounting') {
            when {
                expression { params.SERVICES == 'all' || params.SERVICES == 'accounting' }
            }
            steps {
                script {
                    def image = "${env.ACCOUNTING_IMAGE}:${env.FINAL_TAG}"
                    sh """
                        docker build \\
                            -t ${image} \\
                            -f src/accounting/Dockerfile \\
                            .
                        docker push ${image}
                        docker tag ${image} ${env.ACCOUNTING_IMAGE}:latest
                        docker push ${env.ACCOUNTING_IMAGE}:latest
                    """
                    echo "Pushed: ${image}"
                }
            }
        }

        stage('Build & Push: Cart') {
            when {
                expression { params.SERVICES == 'all' || params.SERVICES == 'cart' }
            }
            steps {
                script {
                    def image = "${env.CART_IMAGE}:${env.FINAL_TAG}"
                    sh """
                        docker build \\
                            -t ${image} \\
                            -f src/cart/src/Dockerfile \\
                            .
                        docker push ${image}
                        docker tag ${image} ${env.CART_IMAGE}:latest
                        docker push ${env.CART_IMAGE}:latest
                    """
                    echo "Pushed: ${image}"
                }
            }
        }

        stage('Cleanup') {
            steps {
                script {
                    // Remove local images to keep the agent disk clean
                    def services = [
                        [name: 'accounting', image: env.ACCOUNTING_IMAGE],
                        [name: 'cart',       image: env.CART_IMAGE]
                    ]
                    services.each { svc ->
                        sh "docker rmi ${svc.image}:${env.FINAL_TAG} ${svc.image}:latest || true"
                    }
                }
            }
        }
    }

    post {
        success {
            echo "All selected .NET services built and pushed successfully with tag: ${env.FINAL_TAG}"
        }
        failure {
            echo "Build failed — check logs above for details."
        }
        always {
            cleanWs()
        }
    }
}
