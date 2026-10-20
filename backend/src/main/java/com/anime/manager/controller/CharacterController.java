package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.CharacterSimpleDTO;
import com.anime.manager.service.CharacterQueryService;
import com.github.pagehelper.PageInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 角色查询控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/character")
@RequiredArgsConstructor
public class CharacterController {
    
    private final CharacterQueryService characterQueryService;
    
    /**
     * 分页查询角色列表
     * 
     * @param pageNum 页码（从1开始，默认1）
     * @param pageSize 每页数量（默认10）
     * @param name 角色名称（可选，支持模糊匹配英文或日文名称）
     * @return 分页结果
     */
    @GetMapping("/list")
    public Result<PageInfo<CharacterSimpleDTO>> getCharactersPage(
            @RequestParam(required = false, defaultValue = "1") Integer pageNum,
            @RequestParam(required = false, defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String name) {
        
        log.info("请求查询角色列表: pageNum={}, pageSize={}, name={}", pageNum, pageSize, name);
        
        PageInfo<CharacterSimpleDTO> pageInfo = characterQueryService.getCharacterPage(pageNum, pageSize, name);
        return Result.success("查询成功", pageInfo);
    }
}
