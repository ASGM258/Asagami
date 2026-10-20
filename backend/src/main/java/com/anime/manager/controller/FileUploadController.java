package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.mapper.UserMapper;
import com.anime.manager.util.AliyunOssUtil;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件上传控制器
 */
@Slf4j
@RestController
@RequestMapping("api/upload")
@RequiredArgsConstructor
public class FileUploadController {
    
    private final AliyunOssUtil aliyunOssUtil;
    private final UserMapper userMapper;
    
    /**
     * 上传图片（默认存储到 images/日期/ 目录）
     * 
     * @param file 图片文件
     * @return 图片URL
     */
    @PostMapping("/image")
    public Result<String> uploadImage(@RequestParam("file") MultipartFile file) {
        log.info("接收到图片上传请求: {}", file.getOriginalFilename());
        
        // 验证文件类型
        String contentType = file.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            return Result.error(400, "只支持上传图片文件");
        }
        
        // 验证文件大小（限制5MB）
        if (file.getSize() > 5 * 1024 * 1024) {
            return Result.error(400, "图片大小不能超过5MB");
        }
        
        try {
            String url = aliyunOssUtil.uploadFile(file);
            log.info("图片上传成功: {}", url);
            return Result.success("上传成功", url);
        } catch (Exception e) {
            log.error("图片上传失败: {}", e.getMessage(), e);
            return Result.error("图片上传失败: " + e.getMessage());
        }
    }
    
    /**
     * 上传头像（存储到 avatars/ 目录）
     * 
     * @param file 头像文件
     * @param request HTTP请求（用于获取当前用户ID）
     * @return 头像URL
     */
    @PostMapping("/avatar")
    public Result<String> uploadAvatar(@RequestParam("avatar") MultipartFile file, HttpServletRequest request) {
        log.info("接收到头像上传请求: {}", file.getOriginalFilename());
        
        // 验证文件类型
        String contentType = file.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            return Result.error(400, "只支持上传图片文件");
        }
        
        // 验证文件大小（限制2MB）
        if (file.getSize() > 2 * 1024 * 1024) {
            return Result.error(400, "头像大小不能超过2MB");
        }
        
        try {
            // 上传到OSS
            String url = aliyunOssUtil.uploadFile(file, "avatars");
            log.info("头像上传成功: {}", url);
            
            // 获取当前用户ID
            Long userId = (Long) request.getAttribute("userId");
            if (userId != null) {
                // 更新数据库中的头像URL
                userMapper.updateAvatar(userId, url);
                log.info("用户头像URL已更新到数据库: userId={}, url={}", userId, url);
            } else {
                log.warn("无法获取用户ID，跳过数据库更新");
            }
            
            return Result.success("上传成功", url);
        } catch (Exception e) {
            log.error("头像上传失败: {}", e.getMessage(), e);
            return Result.error("头像上传失败: " + e.getMessage());
        }
    }
    
    /**
     * 上传动漫封面（存储到 covers/ 目录）
     * 
     * @param file 封面文件
     * @return 封面URL
     */
    @PostMapping("/cover")
    public Result<String> uploadCover(@RequestParam("file") MultipartFile file) {
        log.info("接收到封面上传请求: {}", file.getOriginalFilename());
        
        // 验证文件类型
        String contentType = file.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            return Result.error(400, "只支持上传图片文件");
        }
        
        // 验证文件大小（限制10MB）
        if (file.getSize() > 10 * 1024 * 1024) {
            return Result.error(400, "封面大小不能超过10MB");
        }
        
        try {
            String url = aliyunOssUtil.uploadFile(file, "covers");
            log.info("封面上传成功: {}", url);
            return Result.success("上传成功", url);
        } catch (Exception e) {
            log.error("封面上传失败: {}", e.getMessage(), e);
            return Result.error("封面上传失败: " + e.getMessage());
        }
    }
    
    /**
     * 删除文件
     * 
     * @param fileUrl 文件URL
     * @return 删除结果
     */
    @DeleteMapping("/file")
    public Result<Void> deleteFile(@RequestParam("url") String fileUrl) {
        log.info("接收到文件删除请求: {}", fileUrl);
        
        try {
            aliyunOssUtil.deleteFile(fileUrl);
            return Result.success("删除成功", null);
        } catch (Exception e) {
            log.error("文件删除失败: {}", e.getMessage(), e);
            return Result.error("文件删除失败: " + e.getMessage());
        }
    }
}
