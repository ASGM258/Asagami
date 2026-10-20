package com.anime.manager.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.model.ObjectMetadata;
import com.aliyun.oss.model.PutObjectResult;
import com.anime.manager.config.AliyunOssProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.UUID;

/**
 * 阿里云OSS工具类
 * 提供文件上传、删除等功能
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AliyunOssUtil {
    
    private final AliyunOssProperties ossProperties;
    
    /**
     * 上传文件到OSS
     * 
     * @param file 文件
     * @return 文件访问URL
     */
    public String uploadFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件不能为空");
        }
        
        // 生成文件名
        String originalFilename = file.getOriginalFilename();
        String extension = getFileExtension(originalFilename);
        String fileName = generateFileName(extension);
        
        // 按日期分类存储
        String datePath = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy/MM/dd"));
        String objectName = "images/" + datePath + "/" + fileName;
        
        OSS ossClient = null;
        try {
            // 创建OSS客户端
            ossClient = new OSSClientBuilder().build(
                    ossProperties.getEndpoint(),
                    ossProperties.getAccessKeyId(),
                    ossProperties.getAccessKeySecret()
            );
            
            // 设置元数据
            ObjectMetadata metadata = new ObjectMetadata();
            metadata.setContentType(file.getContentType());
            metadata.setContentLength(file.getSize());
            
            // 上传文件
            InputStream inputStream = file.getInputStream();
            PutObjectResult result = ossClient.putObject(
                    ossProperties.getBucketName(),
                    objectName,
                    inputStream,
                    metadata
            );
            
            log.info("文件上传成功: {}", objectName);
            
            // 返回文件访问URL
            return getFileUrl(objectName);
            
        } catch (IOException e) {
            log.error("文件上传失败: {}", e.getMessage(), e);
            throw new RuntimeException("文件上传失败: " + e.getMessage());
        } finally {
            if (ossClient != null) {
                ossClient.shutdown();
            }
        }
    }
    
    /**
     * 上传文件到OSS（指定目录）
     * 
     * @param file 文件
     * @param directory 目录路径，例如：avatars、covers
     * @return 文件访问URL
     */
    public String uploadFile(MultipartFile file, String directory) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件不能为空");
        }
        
        // 生成文件名
        String originalFilename = file.getOriginalFilename();
        String extension = getFileExtension(originalFilename);
        String fileName = generateFileName(extension);
        
        // 构建对象名称
        String objectName = directory + "/" + fileName;
        
        OSS ossClient = null;
        try {
            // 创建OSS客户端
            ossClient = new OSSClientBuilder().build(
                    ossProperties.getEndpoint(),
                    ossProperties.getAccessKeyId(),
                    ossProperties.getAccessKeySecret()
            );
            
            // 设置元数据
            ObjectMetadata metadata = new ObjectMetadata();
            metadata.setContentType(file.getContentType());
            metadata.setContentLength(file.getSize());
            
            // 上传文件
            InputStream inputStream = file.getInputStream();
            ossClient.putObject(
                    ossProperties.getBucketName(),
                    objectName,
                    inputStream,
                    metadata
            );
            
            log.info("文件上传成功: {}", objectName);
            
            // 返回文件访问URL
            return getFileUrl(objectName);
            
        } catch (IOException e) {
            log.error("文件上传失败: {}", e.getMessage(), e);
            throw new RuntimeException("文件上传失败: " + e.getMessage());
        } finally {
            if (ossClient != null) {
                ossClient.shutdown();
            }
        }
    }
    
    /**
     * 删除OSS上的文件
     * 
     * @param fileUrl 文件URL
     */
    public void deleteFile(String fileUrl) {
        if (fileUrl == null || fileUrl.isEmpty()) {
            return;
        }
        
        // 从URL中提取objectName
        String objectName = extractObjectName(fileUrl);
        if (objectName == null) {
            log.warn("无法解析文件URL: {}", fileUrl);
            return;
        }
        
        OSS ossClient = null;
        try {
            // 创建OSS客户端
            ossClient = new OSSClientBuilder().build(
                    ossProperties.getEndpoint(),
                    ossProperties.getAccessKeyId(),
                    ossProperties.getAccessKeySecret()
            );
            
            // 删除文件
            ossClient.deleteObject(ossProperties.getBucketName(), objectName);
            log.info("文件删除成功: {}", objectName);
            
        } catch (Exception e) {
            log.error("文件删除失败: {}", e.getMessage(), e);
        } finally {
            if (ossClient != null) {
                ossClient.shutdown();
            }
        }
    }
    
    /**
     * 生成唯一文件名
     * 
     * @param extension 文件扩展名
     * @return 唯一文件名
     */
    private String generateFileName(String extension) {
        return UUID.randomUUID().toString().replace("-", "") + extension;
    }
    
    /**
     * 获取文件扩展名
     * 
     * @param filename 文件名
     * @return 扩展名（包含点号），例如：.jpg
     */
    private String getFileExtension(String filename) {
        if (filename == null || filename.lastIndexOf(".") == -1) {
            return "";
        }
        return filename.substring(filename.lastIndexOf(".")).toLowerCase();
    }
    
    /**
     * 获取文件访问URL
     * 
     * @param objectName 对象名称
     * @return 完整的访问URL
     */
    private String getFileUrl(String objectName) {
        String domain = ossProperties.getDomain();
        if (domain != null && !domain.isEmpty()) {
            return domain + "/" + objectName;
        } else {
            // 使用OSS默认域名
            return "https://" + ossProperties.getBucketName() + "." + 
                   ossProperties.getEndpoint() + "/" + objectName;
        }
    }
    
    /**
     * 从URL中提取objectName
     * 
     * @param fileUrl 文件URL
     * @return objectName
     */
    private String extractObjectName(String fileUrl) {
        try {
            String domain = ossProperties.getDomain();
            if (domain != null && !domain.isEmpty() && fileUrl.startsWith(domain)) {
                return fileUrl.substring(domain.length() + 1);
            }
            
            // 尝试从OSS默认域名提取
            String ossDomain = "https://" + ossProperties.getBucketName() + "." + 
                              ossProperties.getEndpoint() + "/";
            if (fileUrl.startsWith(ossDomain)) {
                return fileUrl.substring(ossDomain.length());
            }
            
            return null;
        } catch (Exception e) {
            log.error("提取objectName失败: {}", e.getMessage());
            return null;
        }
    }
}
