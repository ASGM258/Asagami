package com.anime.manager.mapper;

import com.anime.manager.entity.UserFavoriteCharacter;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 用户喜欢角色Mapper接口
 */
@Mapper
public interface UserFavoriteCharacterMapper {
    
    /**
     * 根据用户ID和角色ID查询喜欢记录
     * 
     * @param userId 用户ID
     * @param characterId 角色ID
     * @return 喜欢记录，不存在则返回null
     */
    UserFavoriteCharacter findByUserIdAndCharacterId(@Param("userId") Long userId, @Param("characterId") Long characterId);
    
    /**
     * 插入喜欢记录
     * 
     * @param userFavoriteCharacter 喜欢记录
     * @return 影响行数
     */
    int insert(UserFavoriteCharacter userFavoriteCharacter);
    
    /**
     * 更新喜欢记录（动态SQL）
     * 只更新非null字段
     * 
     * @param userFavoriteCharacter 喜欢记录
     * @return 影响行数
     */
    int updateSelective(UserFavoriteCharacter userFavoriteCharacter);
}
