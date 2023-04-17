package io.daocloud.dataservice.repository;

import io.daocloud.dataservice.entity.Advertise;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

// This will be AUTO IMPLEMENTED by Spring into a Bean called userRepository
// CRUD refers Create, Read, Update, Delete
public interface AdvertiseRepository extends CrudRepository<Advertise, Integer> {
    Iterable<Advertise> findByAdKey(@Param("adKey") String adKey);
}
