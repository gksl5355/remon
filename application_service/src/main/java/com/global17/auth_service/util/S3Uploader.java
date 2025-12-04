package com.global17.auth_service.util;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

@Component
public class S3Uploader {

    @Value("${aws.accessKeyId}")
    private String accessKey;
    @Value("${aws.secretAccessKey}")
    private String secretKey;
    @Value("${aws.region}")
    private String region;
    
    @Value("${aws.s3.target-arn}")
    private String targetArn;
    
    @Value("${aws.s3.base-prefix}")
    private String basePrefix;
    @Value("${aws.s3.app-prefix}")
    private String appPrefix;

    private S3Client s3Client;

    @PostConstruct
    public void init() {
        this.s3Client = S3Client.builder()
                .region(Region.of(region))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(accessKey, secretKey)))
                .build();
    }

    public String uploadFile(byte[] content, String fileName, String category) {
        // 경로 조립: base/app/category/filename
        String s3Key = String.format("%s/%s/%s/%s", basePrefix, appPrefix, category, fileName)
                .replaceAll("//+", "/"); // 중복 슬래시 제거

        try {
            System.out.println("☁️ S3 Uploading: " + s3Key);
            
            s3Client.putObject(PutObjectRequest.builder()
                    .bucket(targetArn) // Access Point ARN 사용
                    .key(s3Key)
                    .build(), RequestBody.fromBytes(content));
            
            return "s3://" + s3Key;
        } catch (Exception e) {
            System.err.println("❌ S3 Upload Failed: " + e.getMessage());
            return null;
        }
    }
}




