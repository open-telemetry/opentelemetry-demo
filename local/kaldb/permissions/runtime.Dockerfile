FROM amazoncorretto:21-al2023@sha256:90100f194336ef2326f5efe1ee747395fd87d8210ad6d60463196aa0c4b0ad4e
COPY .state/runtime/ /runtime/
RUN curl --version
ENTRYPOINT ["java"]
