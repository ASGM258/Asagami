package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.CharacterSimpleDTO;
import com.anime.manager.dto.UserFavoriteCharacterRequest;
import com.anime.manager.service.CharacterQueryService;
import com.anime.manager.service.UserFavoriteCharacterService;
import com.github.pagehelper.PageInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 用户喜欢角色控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/character/favorite")
@RequiredArgsConstructor
public class UserFavoriteCharacterController {
    
    private final UserFavoriteCharacterService userFavoriteCharacterService;
    private final CharacterQueryService characterQueryService;
    
    /**
     * 更新或创建用户喜欢角色记录
     * 
     * @param request 请求（包含角色ID和喜欢状态）
     * @return 操作结果
     */
    @PostMapping("/update")
    public Result<Boolean> updateUserFavoriteCharacter(@RequestBody UserFavoriteCharacterRequest request) {
        log.info("收到更新喜欢角色请求: characterId={}, favoriteStatus={}", 
                request.getCharacterId(), request.getFavoriteStatus());
        
        try {
            boolean success = userFavoriteCharacterService.updateOrCreateUserFavoriteCharacter(
                request.getCharacterId(), 
                request.getFavoriteStatus()
            );
            
            if (success) {
                String message = request.getFavoriteStatus() == 1 ? "喜欢成功" : "取消喜欢成功";
                return Result.success(message, true);
            } else {
                return Result.error("更新失败");
            }
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("更新喜欢记录失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 查询用户喜欢角色历史（分页）
     * 
     * @param pageNum 页码，默认1
     * @param pageSize 每页大小，默认10
     * @param name 角色名称搜索关键词（可选）
     * @return 分页结果
     */
    @GetMapping("/history")
    public Result<PageInfo<CharacterSimpleDTO>> getUserFavoriteCharacterHistory(
            @RequestParam(required = false, defaultValue = "1") Integer pageNum,
            @RequestParam(required = false, defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String name) {
        log.info("收到喜欢角色历史查询请求: pageNum={}, pageSize={}, name={}", pageNum, pageSize, name);
        
        try {
            PageInfo<CharacterSimpleDTO> pageInfo = characterQueryService.getUserFavoriteCharacterHistory(pageNum, pageSize, name);
            return Result.success(pageInfo);
        } catch (RuntimeException e) {
            log.error("喜欢角色历史查询失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
}
