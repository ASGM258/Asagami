package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.CharacterDetailQueryRequest;
import com.anime.manager.service.CharacterQueryService;
import com.anime.manager.vo.CharacterDetailVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 角色查询控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/character")
@RequiredArgsConstructor
public class CharacterQueryController {
    
    private final CharacterQueryService characterQueryService;
    
    /**
     * 查询角色详情（包含角色信息和评论列表）
     * 
     * @param request 查询请求（包含角色ID）
     * @return 角色详情VO
     */
    @PostMapping("/detail")
    public Result<CharacterDetailVO> getCharacterDetail(@Valid @RequestBody CharacterDetailQueryRequest request) {
        log.info("收到角色详情查询请求: characterId={}", request.getCharacterId());
        
        try {
            CharacterDetailVO detail = characterQueryService.getCharacterDetail(request.getCharacterId());
            return Result.success(detail);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("查询角色详情失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
}
